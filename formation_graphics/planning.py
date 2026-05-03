from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .config_model import MatchConfig, PlayerConfig, load_match_config, parse_match_config

DEFAULT_LOCAL_CONFIG_PATH = Path("config/game_config.local.json")
DEFAULT_EXAMPLE_CONFIG_PATH = Path("config/game_config.example.json")

OUTFIELD_POSITIONS = ["LB", "RB", "LM", "CM", "RM", "ST"]
ALL_POSITIONS = ["GK", *OUTFIELD_POSITIONS]
MIRROR = {"LB": "RB", "RB": "LB", "LM": "RM", "RM": "LM"}
GROUP = {
    "LB": "DEF",
    "RB": "DEF",
    "LM": "MID",
    "CM": "MID",
    "RM": "MID",
    "ST": "ATT",
}


@dataclass(frozen=True)
class SegmentPlan:
    half: int
    half_segment_index: int
    global_block: int
    start_min: float
    end_min: float
    lineup: Dict[str, str]  # position -> player


@dataclass(frozen=True)
class MatchPlan:
    segments: List[SegmentPlan]
    global_block_count: int


def ensure_match_config(cfg: MatchConfig | dict[str, Any]) -> MatchConfig:
    if isinstance(cfg, MatchConfig):
        return cfg
    return parse_match_config(cfg)


def load_game_config(config_path: Path) -> MatchConfig:
    return load_match_config(config_path, DEFAULT_EXAMPLE_CONFIG_PATH)


def validate_config(cfg: MatchConfig | dict[str, Any]) -> None:
    ensure_match_config(cfg)


def choose_global_block_count(non_goalie_count: int) -> int:
    return non_goalie_count // math.gcd(5, non_goalie_count)


def build_non_goalie_targets(
    non_goalies: List[str],
    global_block_count: int,
    kickoff_non_goalies: List[str],
    order_index: Dict[str, int],
) -> Dict[str, int]:
    total_slots = 5 * global_block_count
    m = len(non_goalies)
    base = total_slots // m
    extra = total_slots % m

    ranked = sorted(
        non_goalies,
        key=lambda p: (
            0 if p in kickoff_non_goalies else 1,
            order_index[p],
        ),
    )

    targets = {p: base for p in non_goalies}
    for p in ranked[:extra]:
        targets[p] += 1

    for p in kickoff_non_goalies:
        targets[p] = max(targets[p], 1)

    delta = sum(targets.values()) - total_slots
    if delta > 0:
        reducible = sorted(
            non_goalies,
            key=lambda p: (
                p in kickoff_non_goalies,
                order_index[p],
            ),
            reverse=True,
        )
        for p in reducible:
            while delta > 0 and targets[p] > (1 if p in kickoff_non_goalies else 0):
                targets[p] -= 1
                delta -= 1
            if delta == 0:
                break

    if sum(targets.values()) != total_slots:
        raise RuntimeError("Could not construct valid non-goalie targets")

    return targets


def choose_combo_for_slot(
    candidates: List[str],
    remaining: Dict[str, int],
    slots_left_after: int,
    kickoff_non_goalies: set[str],
    global_block_idx: int,
    order_index: Dict[str, int],
) -> Tuple[str, ...]:
    best_combo = None
    best_score = None

    for combo in itertools.combinations(candidates, 5):
        combo_set = set(combo)

        feasible = True
        for p in candidates:
            need_after = remaining[p] - (1 if p in combo_set else 0)
            if need_after < 0 or need_after > slots_left_after:
                feasible = False
                break
        if not feasible:
            continue

        selected_need = sum(remaining[p] for p in combo)
        early_bonus = 0
        if global_block_idx in (1, 2):
            early_bonus = sum(1 for p in combo if p in kickoff_non_goalies)
        order_bonus = -sum(order_index[p] for p in combo)

        score = (selected_need, early_bonus, order_bonus)
        if best_score is None or score > best_score:
            best_score = score
            best_combo = combo

    if best_combo is None:
        raise RuntimeError("No feasible combo found for block")

    return best_combo


def preference_penalty(player: str, position: str, players_cfg: dict[str, PlayerConfig]) -> int:
    prefs = players_cfg[player].positions

    if position in prefs:
        return prefs.index(position) * 10

    mirror = MIRROR.get(position)
    if mirror and mirror in prefs:
        return prefs.index(mirror) * 10 + 2

    same_line_idxs = [idx for idx, p in enumerate(prefs) if GROUP[p] == GROUP[position]]
    if same_line_idxs:
        return min(same_line_idxs) * 10 + 6

    return 100


def assign_positions_for_segment(
    outfield_players: List[str], players_cfg: dict[str, PlayerConfig]
) -> Dict[str, str]:
    best_perm = None
    best_score = None

    for perm in itertools.permutations(outfield_players, len(OUTFIELD_POSITIONS)):
        score = 0
        for pos, player in zip(OUTFIELD_POSITIONS, perm):
            score += preference_penalty(player, pos, players_cfg)
        tie = tuple(perm)
        candidate = (score, tie)
        if best_score is None or candidate < best_score:
            best_score = candidate
            best_perm = perm

    assert best_perm is not None
    return {pos: player for pos, player in zip(OUTFIELD_POSITIONS, best_perm)}


def build_schedule(cfg: MatchConfig | dict[str, Any]) -> Tuple[List[SegmentPlan], int]:
    match = ensure_match_config(cfg)

    players = list(match.players.keys())
    order_index = {p: i for i, p in enumerate(players)}

    gk1 = match.gk1
    gk2 = match.gk2
    halftime = match.game_minutes / 2

    non_goalies = [p for p in players if p not in {gk1, gk2}]
    kickoff_non_goalies = [p for p in match.kickoff_starters if p not in {gk1, gk2}]

    global_block_count = choose_global_block_count(len(non_goalies))
    global_block_minutes = match.game_minutes / global_block_count

    targets = build_non_goalie_targets(
        non_goalies, global_block_count, kickoff_non_goalies, order_index
    )
    remaining = dict(targets)

    block_non_goalies: List[Tuple[str, ...]] = []
    for global_idx in range(global_block_count):
        if global_idx == 0:
            selected_non_goalies = tuple(kickoff_non_goalies)
            if len(selected_non_goalies) != 5:
                raise RuntimeError("kickoff starters must include exactly 5 non-goalies")
        else:
            slots_left_after = global_block_count - (global_idx + 1)
            selected_non_goalies = choose_combo_for_slot(
                candidates=non_goalies,
                remaining=remaining,
                slots_left_after=slots_left_after,
                kickoff_non_goalies=set(kickoff_non_goalies),
                global_block_idx=global_idx,
                order_index=order_index,
            )

        for p in selected_non_goalies:
            remaining[p] -= 1
            if remaining[p] < 0:
                raise RuntimeError(f"Invalid schedule: over-assigned {p}")

        block_non_goalies.append(selected_non_goalies)

    if any(v != 0 for v in remaining.values()):
        raise RuntimeError(f"Invalid schedule, leftover non-goalie targets: {remaining}")

    segments: List[SegmentPlan] = []
    half_counters = {1: 0, 2: 0}

    for global_idx, selected_non_goalies in enumerate(block_non_goalies):
        block_start = global_idx * global_block_minutes
        block_end = (global_idx + 1) * global_block_minutes

        if block_end <= halftime:
            outfield_assignment = assign_positions_for_segment(
                [gk2, *selected_non_goalies], match.players
            )
            half_counters[1] += 1
            segments.append(
                SegmentPlan(
                    half=1,
                    half_segment_index=half_counters[1],
                    global_block=global_idx + 1,
                    start_min=block_start,
                    end_min=block_end,
                    lineup={"GK": gk1, **outfield_assignment},
                )
            )
        elif block_start >= halftime:
            outfield_assignment = assign_positions_for_segment(
                [gk1, *selected_non_goalies], match.players
            )
            half_counters[2] += 1
            segments.append(
                SegmentPlan(
                    half=2,
                    half_segment_index=half_counters[2],
                    global_block=global_idx + 1,
                    start_min=block_start,
                    end_min=block_end,
                    lineup={"GK": gk2, **outfield_assignment},
                )
            )
        else:
            outfield_h1 = assign_positions_for_segment([gk2, *selected_non_goalies], match.players)
            gk2_pos = next(pos for pos, player in outfield_h1.items() if player == gk2)
            outfield_h2 = dict(outfield_h1)
            outfield_h2[gk2_pos] = gk1

            half_counters[1] += 1
            segments.append(
                SegmentPlan(
                    half=1,
                    half_segment_index=half_counters[1],
                    global_block=global_idx + 1,
                    start_min=block_start,
                    end_min=halftime,
                    lineup={"GK": gk1, **outfield_h1},
                )
            )

            half_counters[2] += 1
            segments.append(
                SegmentPlan(
                    half=2,
                    half_segment_index=half_counters[2],
                    global_block=global_idx + 1,
                    start_min=halftime,
                    end_min=block_end,
                    lineup={"GK": gk2, **outfield_h2},
                )
            )

    return segments, global_block_count


def plan_match(
    cfg: MatchConfig | dict[str, Any],
    strategy: str = "heuristic",
    solver_adapter: Callable[..., Tuple[List[SegmentPlan], int]] | None = None,
    **strategy_options,
) -> MatchPlan:
    match = ensure_match_config(cfg)

    if strategy == "heuristic":
        segments, global_block_count = build_schedule(match)
    elif strategy == "solver":
        if solver_adapter is None:
            raise ValueError("solver strategy requires a solver_adapter")
        segments, global_block_count = solver_adapter(match, **strategy_options)
    else:
        raise ValueError(f"Unknown planning strategy: {strategy}")

    return MatchPlan(segments=segments, global_block_count=global_block_count)
