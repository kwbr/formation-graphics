#!/usr/bin/env python3
"""7v7 formation + substitution graphics generator.

Rules implemented from spec:
- 40-minute game, 2 halves (20 each)
- Formation slots each segment: GK, LB, RB, LM, CM, RM, ST
- Unlimited rolling subs, but only at block boundaries
- Roster size must be 7..11
- gk1 is GK in half 1, gk2 is GK in half 2
- gk1 and gk2 both play full game (GK one half, outfield opposite half)
- kickoff_starters must contain exactly 7 names (including gk1 and gk2)
- Position preferences are soft (ordered list), with mirrored fallback (LB<->RB, LM<->RM)
- Deterministic scheduling
- Block boundaries are global for the full 40 minutes (not forced to halftime)

Outputs in output/<game_id>/:
- h1_segmentXX.png, h2_segmentXX.png
- schedule.csv
- summary.txt
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle


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


def load_game_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Create it from {DEFAULT_EXAMPLE_CONFIG_PATH} and keep it untracked."
        )

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file: {config_path} ({exc})") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a JSON object: {config_path}")

    return data


def validate_config(cfg: dict) -> None:
    errors: List[str] = []

    players = list(cfg.get("players", {}).keys())
    unique_players = set(players)

    if not isinstance(cfg.get("game_minutes"), int) or cfg["game_minutes"] <= 0:
        errors.append("game_minutes must be a positive integer")

    if len(players) != len(unique_players):
        errors.append("players contains duplicate names")

    if not (7 <= len(players) <= 11):
        errors.append(f"player count must be 7..11, got {len(players)}")

    gk1 = cfg.get("gk1")
    gk2 = cfg.get("gk2")
    if gk1 not in unique_players:
        errors.append(f"gk1 '{gk1}' is not in players")
    if gk2 not in unique_players:
        errors.append(f"gk2 '{gk2}' is not in players")
    if gk1 == gk2:
        errors.append("gk1 and gk2 must be different players")

    starters = cfg.get("kickoff_starters", [])
    if not isinstance(starters, list):
        errors.append("kickoff_starters must be a list")
    else:
        if len(starters) != 7:
            errors.append(f"kickoff_starters must have exactly 7 names, got {len(starters)}")
        if len(starters) != len(set(starters)):
            errors.append("kickoff_starters contains duplicates")
        unknown = [s for s in starters if s not in unique_players]
        if unknown:
            errors.append(f"kickoff_starters has unknown players: {unknown}")
        if gk1 not in starters:
            errors.append("kickoff_starters must include gk1")
        if gk2 not in starters:
            errors.append("kickoff_starters must include gk2")

    for name, info in cfg.get("players", {}).items():
        prefs = info.get("positions")
        if not isinstance(prefs, list) or not prefs:
            errors.append(f"{name}: positions must be a non-empty list")
            continue
        invalid = [p for p in prefs if p not in OUTFIELD_POSITIONS]
        if invalid:
            errors.append(f"{name}: invalid preferred positions: {invalid}")

    if errors:
        raise ValueError("Invalid GAME_CONFIG:\n- " + "\n- ".join(errors))


def choose_global_block_count(non_goalie_count: int) -> int:
    """Smallest block count with perfect non-goalie fairness in block slots.

    We allocate 5 non-goalie spots per block. Perfect fairness in block counts
    happens when (5 * blocks) is divisible by non_goalie_count.
    """

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

    # Deterministic: starters first, then config order.
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

    # kickoff block forces these 5 non-goalies to play at least once
    for p in kickoff_non_goalies:
        targets[p] = max(targets[p], 1)

    # Adjust total if kickoff min bumped some values.
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
    # Choose 5 players for this block.
    best_combo = None
    best_score = None

    for combo in itertools.combinations(candidates, 5):
        combo_set = set(combo)

        # Feasibility: after taking this slot, no one can require > remaining slots.
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


def preference_penalty(player: str, position: str, players_cfg: dict) -> int:
    prefs = players_cfg[player]["positions"]

    if position in prefs:
        return prefs.index(position) * 10

    mirror = MIRROR.get(position)
    if mirror and mirror in prefs:
        return prefs.index(mirror) * 10 + 2

    same_line_idxs = [idx for idx, p in enumerate(prefs) if GROUP[p] == GROUP[position]]
    if same_line_idxs:
        return min(same_line_idxs) * 10 + 6

    return 100


def assign_positions_for_segment(outfield_players: List[str], players_cfg: dict) -> Dict[str, str]:
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


def build_schedule(cfg: dict) -> Tuple[List[SegmentPlan], int]:
    players = list(cfg["players"].keys())
    order_index = {p: i for i, p in enumerate(players)}

    gk1 = cfg["gk1"]
    gk2 = cfg["gk2"]
    halftime = cfg["game_minutes"] / 2

    non_goalies = [p for p in players if p not in {gk1, gk2}]
    kickoff_non_goalies = [p for p in cfg["kickoff_starters"] if p not in {gk1, gk2}]

    global_block_count = choose_global_block_count(len(non_goalies))
    global_block_minutes = cfg["game_minutes"] / global_block_count

    targets = build_non_goalie_targets(non_goalies, global_block_count, kickoff_non_goalies, order_index)
    remaining = dict(targets)

    # First choose non-goalie groups per global block.
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

    # Then split global blocks by halftime if needed.
    segments: List[SegmentPlan] = []
    half_counters = {1: 0, 2: 0}

    for global_idx, selected_non_goalies in enumerate(block_non_goalies):
        block_start = global_idx * global_block_minutes
        block_end = (global_idx + 1) * global_block_minutes

        if block_end <= halftime:
            outfield_assignment = assign_positions_for_segment([gk2, *selected_non_goalies], cfg["players"])
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
            outfield_assignment = assign_positions_for_segment([gk1, *selected_non_goalies], cfg["players"])
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
            # Block crosses halftime: keep the same 5 rotating players after break.
            # Preserve their positions across halftime, and swap the locked outfield goalie.
            outfield_h1 = assign_positions_for_segment([gk2, *selected_non_goalies], cfg["players"])
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


def pitch_positions() -> Dict[str, Tuple[float, float]]:
    # Goal at the bottom, attacking toward the top.
    return {
        "GK": (0.50, 0.08),
        "LB": (0.30, 0.30),
        "RB": (0.70, 0.30),
        "LM": (0.20, 0.55),
        "CM": (0.50, 0.55),
        "RM": (0.80, 0.55),
        "ST": (0.50, 0.82),
    }


def draw_segment_on_axis(
    ax,
    segment: SegmentPlan,
    all_players: List[str],
    incoming_players: set[str] | None = None,
    moved_players: set[str] | None = None,
    compact: bool = False,
) -> None:
    coords = pitch_positions()
    # Black-and-white print friendly pitch styling.
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#f4f4f4", edgecolor="black", linewidth=2))
    ax.plot([0, 1], [0.5, 0.5], color="black", linewidth=1.2)
    ax.add_patch(Circle((0.5, 0.5), 0.08, fill=False, edgecolor="black", linewidth=1.0))
    ax.add_patch(Rectangle((0.2, 0), 0.6, 0.12, fill=False, edgecolor="black", linewidth=1.0))

    incoming_players = incoming_players or set()
    moved_players = moved_players or set()

    marker_r = 0.045 if not compact else 0.04
    font_size = 9 if not compact else 7

    for pos in ALL_POSITIONS:
        player = segment.lineup[pos]
        x, y = coords[pos]

        ax.add_patch(Circle((x, y), marker_r, facecolor="white", edgecolor="black", linewidth=1.2))

        # Solid outer ring = player coming on.
        if player in incoming_players:
            ax.add_patch(Circle((x, y), marker_r + 0.013, fill=False, edgecolor="black", linewidth=2.2))
        # Dashed outer ring = player changed position.
        if player in moved_players:
            ax.add_patch(
                Circle(
                    (x, y),
                    marker_r + 0.021,
                    fill=False,
                    edgecolor="black",
                    linewidth=1.8,
                    linestyle=(0, (3, 2)),
                )
            )

        ax.text(x, y, f"{pos}\n{player}", ha="center", va="center", color="black", fontsize=font_size, weight="bold")

    on_field = set(segment.lineup.values())
    bench = sorted([p for p in all_players if p not in on_field])
    half_offset = 0.0 if segment.half == 1 else 20.0

    if compact:
        ax.set_title(
            f"H{segment.half} S{segment.half_segment_index} ({segment.start_min - half_offset:.1f}-{segment.end_min - half_offset:.1f})",
            fontsize=10,
            weight="bold",
        )
        ax.text(
            0.01,
            -0.08,
            f"Bench: {', '.join(bench) if bench else 'None'}",
            transform=ax.transAxes,
            fontsize=8,
            color="black",
        )
    else:
        ax.text(
            0.01,
            -0.08,
            f"Bench: {', '.join(bench) if bench else 'None'}",
            transform=ax.transAxes,
            fontsize=10,
            color="black",
        )

        incoming_label = ", ".join(sorted(incoming_players)) if incoming_players else "None"
        ax.text(
            0.01,
            -0.13,
            f"Coming on (solid ring): {incoming_label}",            transform=ax.transAxes,
            fontsize=10,
            color="black",
        )

        moved_label = ", ".join(sorted(moved_players)) if moved_players else "None"
        ax.text(
            0.01,
            -0.18,
            f"Position change (dashed ring): {moved_label}",            transform=ax.transAxes,
            fontsize=10,
            color="black",
        )

        title = (
            f"Half {segment.half} Segment {segment.half_segment_index} "
            f"(global {segment.global_block}, abs {segment.start_min:.1f}-{segment.end_min:.1f} min, "
            f"half {segment.start_min - half_offset:.1f}-{segment.end_min - half_offset:.1f})"
        )
        ax.set_title(title, fontsize=14, weight="bold")

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")


def draw_segment_image(
    segment: SegmentPlan,
    all_players: List[str],
    players_cfg: dict,
    out_path: Path,
    incoming_players: set[str] | None = None,
    moved_players: set[str] | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    draw_segment_on_axis(
        ax,
        segment,
        all_players,
        incoming_players=incoming_players,
        moved_players=moved_players,
        compact=False,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def compute_transition_markers(segments: List[SegmentPlan]) -> List[Tuple[set[str], set[str]]]:
    markers: List[Tuple[set[str], set[str]]] = []
    prev_on_field: set[str] | None = None
    prev_player_pos: Dict[str, str] | None = None

    for s in segments:
        current_on_field = set(s.lineup.values())
        current_player_pos = {player: pos for pos, player in s.lineup.items()}

        incoming = set() if prev_on_field is None else (current_on_field - prev_on_field)
        moved = set()
        if prev_player_pos is not None:
            for player in (current_on_field & (prev_on_field or set())):
                if current_player_pos[player] != prev_player_pos.get(player):
                    moved.add(player)

        markers.append((incoming, moved))
        prev_on_field = current_on_field
        prev_player_pos = current_player_pos

    return markers


def write_half_sheets_a4(
    segments: List[SegmentPlan],
    all_players: List[str],
    out_dir: Path,
    game_id: str,
) -> None:
    markers = compute_transition_markers(segments)

    for half in (1, 2):
        idxs = [i for i, s in enumerate(segments) if s.half == half]
        if not idxs:
            continue

        n = len(idxs)
        if n <= 2:
            cols = 1
        elif n <= 4:
            cols = 2
        else:
            cols = 3
        rows = math.ceil(n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(8.27, 11.69))  # A4 portrait
        if hasattr(axes, "flatten"):
            axes_list = list(axes.flatten())
        elif isinstance(axes, list):
            axes_list = axes
        else:
            axes_list = [axes]

        for ax in axes_list:
            ax.axis("off")

        for slot, idx in enumerate(idxs):
            s = segments[idx]
            incoming, moved = markers[idx]
            draw_segment_on_axis(
                axes_list[slot],
                s,
                all_players,
                incoming_players=incoming,
                moved_players=moved,
                compact=True,
            )

        fig.suptitle(
            f"{game_id} - Half {half} Rotation Sheet (A4)\nSolid ring=coming on, dashed ring=position change",
            fontsize=12,
            weight="bold",
        )
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(out_dir / f"half{half}_sheet_a4.pdf")
        fig.savefig(out_dir / f"half{half}_sheet_a4.png", dpi=300)
        plt.close(fig)


def write_schedule_csv(segments: List[SegmentPlan], all_players: List[str], path: Path) -> None:
    fields = [
        "half",
        "half_segment_index",
        "global_block",
        "start_min",
        "end_min",
        "half_start_min",
        "half_end_min",
        *ALL_POSITIONS,
        "bench",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for s in segments:
            on_field = set(s.lineup.values())
            bench = sorted([p for p in all_players if p not in on_field])
            half_offset = 0.0 if s.half == 1 else 20.0
            row = {
                "half": s.half,
                "half_segment_index": s.half_segment_index,
                "global_block": s.global_block,
                "start_min": f"{s.start_min:.2f}",
                "end_min": f"{s.end_min:.2f}",
                "half_start_min": f"{s.start_min - half_offset:.2f}",
                "half_end_min": f"{s.end_min - half_offset:.2f}",
                "bench": ", ".join(bench),
            }
            for pos in ALL_POSITIONS:
                row[pos] = s.lineup[pos]
            writer.writerow(row)


def compute_player_stats(
    segments: List[SegmentPlan],
    all_players: List[str],
    players_cfg: dict,
) -> tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, int], Dict[str, int], Dict[str, int]]:
    total_minutes = {p: 0.0 for p in all_players}
    gk_minutes = {p: 0.0 for p in all_players}
    outfield_minutes = {p: 0.0 for p in all_players}
    pref_deviations = {p: 0 for p in all_players}
    segments_played = {p: 0 for p in all_players}
    segments_benched = {p: 0 for p in all_players}

    for s in segments:
        duration = s.end_min - s.start_min
        on_field = set(s.lineup.values())
        for p in all_players:
            if p in on_field:
                segments_played[p] += 1
            else:
                segments_benched[p] += 1

        for pos, p in s.lineup.items():
            total_minutes[p] += duration
            if pos == "GK":
                gk_minutes[p] += duration
            else:
                outfield_minutes[p] += duration
                prefs = players_cfg[p]["positions"]
                if pos not in prefs and MIRROR.get(pos) not in prefs:
                    pref_deviations[p] += 1

    return total_minutes, gk_minutes, outfield_minutes, pref_deviations, segments_played, segments_benched


def write_player_stats_csv(
    segments: List[SegmentPlan],
    all_players: List[str],
    players_cfg: dict,
    out_path: Path,
) -> None:
    (
        total_minutes,
        gk_minutes,
        outfield_minutes,
        pref_deviations,
        segments_played,
        segments_benched,
    ) = compute_player_stats(segments, all_players, players_cfg)

    fields = [
        "player",
        "total_minutes",
        "gk_minutes",
        "outfield_minutes",
        "segments_played",
        "segments_benched",
        "pref_deviation_segments",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in all_players:
            writer.writerow(
                {
                    "player": p,
                    "total_minutes": f"{total_minutes[p]:.2f}",
                    "gk_minutes": f"{gk_minutes[p]:.2f}",
                    "outfield_minutes": f"{outfield_minutes[p]:.2f}",
                    "segments_played": segments_played[p],
                    "segments_benched": segments_benched[p],
                    "pref_deviation_segments": pref_deviations[p],
                }
            )


def write_summary(
    segments: List[SegmentPlan],
    all_players: List[str],
    players_cfg: dict,
    gk1: str,
    gk2: str,
    game_minutes: int,
    global_block_count: int,
    out_path: Path,
) -> None:
    (
        total_minutes,
        gk_minutes,
        outfield_minutes,
        pref_deviations,
        _segments_played,
        _segments_benched,
    ) = compute_player_stats(segments, all_players, players_cfg)

    non_goalies = [p for p in all_players if p not in {gk1, gk2}]
    non_goalie_outfield = [outfield_minutes[p] for p in non_goalies]
    fairness_gap = max(non_goalie_outfield) - min(non_goalie_outfield) if non_goalie_outfield else 0.0

    lines = []
    lines.append("Formation Scheduler Summary")
    lines.append("=" * 28)
    lines.append(f"Game minutes: {game_minutes}")
    lines.append(f"Global blocks: {global_block_count}")
    lines.append(f"Global block minutes: {game_minutes / global_block_count:.3f}")
    lines.append("Note: blocks are global and can cross halftime.")
    lines.append("")
    lines.append(f"Goalie half assignments: H1={gk1}, H2={gk2}")
    lines.append(f"Non-goalie outfield fairness gap (max-min): {fairness_gap:.3f} minutes")
    lines.append("")
    lines.append("Per-player minutes:")

    for p in all_players:
        lines.append(
            f"- {p}: total={total_minutes[p]:.2f}, GK={gk_minutes[p]:.2f}, "
            f"outfield={outfield_minutes[p]:.2f}, pref_deviation_segments={pref_deviations[p]}"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate(cfg: dict) -> Path:
    validate_config(cfg)

    game_id = cfg["game_id"]
    out_dir = Path("output") / game_id
    out_dir.mkdir(parents=True, exist_ok=True)

    segments, global_block_count = build_schedule(cfg)
    all_players = list(cfg["players"].keys())

    max_h1 = max((s.half_segment_index for s in segments if s.half == 1), default=0)
    max_h2 = max((s.half_segment_index for s in segments if s.half == 2), default=0)
    pad = max(2, len(str(max(max_h1, max_h2, 1))))

    markers = compute_transition_markers(segments)
    for idx, s in enumerate(segments):
        file_name = f"h{s.half}_segment{s.half_segment_index:0{pad}d}.png"
        incoming, moved = markers[idx]
        draw_segment_image(
            s,
            all_players,
            cfg["players"],
            out_dir / file_name,
            incoming_players=incoming,
            moved_players=moved,
        )

    write_half_sheets_a4(segments, all_players, out_dir, game_id)

    write_schedule_csv(segments, all_players, out_dir / "schedule.csv")
    write_player_stats_csv(segments, all_players, cfg["players"], out_dir / "player_stats.csv")
    write_summary(
        segments=segments,
        all_players=all_players,
        players_cfg=cfg["players"],
        gk1=cfg["gk1"],
        gk2=cfg["gk2"],
        game_minutes=cfg["game_minutes"],
        global_block_count=global_block_count,
        out_path=out_dir / "summary.txt",
    )

    return out_dir


def open_images_in_order(out_dir: Path) -> None:
    opener = shutil.which("open")
    if opener is None:
        print("Cannot auto-open images: 'open' command not found on this system.")
        return

    images = sorted(out_dir.glob("h*_segment*.png"))
    if not images:
        images = sorted(out_dir.glob("h*_block*.png"))  # backward compatibility
    if not images:
        print("No segment images found to open.")
        return

    subprocess.run([opener, *[str(p) for p in images]], check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate 7v7 formation graphics and schedule")
    parser.add_argument("--open", action="store_true", help="Open generated segment images after rendering")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_LOCAL_CONFIG_PATH),
        help=f"Path to game config JSON (default: {DEFAULT_LOCAL_CONFIG_PATH})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = load_game_config(Path(args.config))
    output_dir = generate(cfg)
    print(f"Generated files in: {output_dir}")
    if args.open:
        open_images_in_order(output_dir)
