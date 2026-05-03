#!/usr/bin/env python3
"""Solver-based scheduler that prioritizes position stability over fairness.

This script keeps the same output format as main.py but computes lineups with
OR-Tools CP-SAT.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ortools.sat.python import cp_model

from . import planning
from .config_model import MatchConfig
from .planning import ALL_POSITIONS, OUTFIELD_POSITIONS, SegmentPlan
from .publishing import open_images_in_order, publish_outputs


def build_segment_timeline(
    global_block_count: int, game_minutes: int
) -> tuple[list[dict], dict[int, list[int]]]:
    halftime = game_minutes / 2
    global_block_minutes = game_minutes / global_block_count

    segments: list[dict] = []
    by_global: dict[int, list[int]] = {}
    half_counts = {1: 0, 2: 0}

    for g in range(global_block_count):
        start = g * global_block_minutes
        end = (g + 1) * global_block_minutes

        ranges: list[tuple[int, float, float]] = []
        if end <= halftime:
            ranges.append((1, start, end))
        elif start >= halftime:
            ranges.append((2, start, end))
        else:
            ranges.append((1, start, halftime))
            ranges.append((2, halftime, end))

        by_global[g + 1] = []
        for half, seg_start, seg_end in ranges:
            half_counts[half] += 1
            segments.append(
                {
                    "half": half,
                    "half_segment_index": half_counts[half],
                    "global_block": g + 1,
                    "start_min": seg_start,
                    "end_min": seg_end,
                }
            )
            by_global[g + 1].append(len(segments) - 1)

    return segments, by_global


def build_schedule_solver(
    cfg: MatchConfig | dict[str, Any],
    w_pos_change: int = 1000,
    w_sub_toggle: int = 100,
    w_fairness: int = 10,
    w_pref: int = 1,
    fairness_band_blocks: int = 0,
    max_consecutive_bench_blocks: int = 1,
) -> tuple[list[SegmentPlan], int]:
    match = planning.ensure_match_config(cfg)

    players = list(match.players.keys())
    gk1, gk2 = match.gk1, match.gk2
    non_goalies = [p for p in players if p not in {gk1, gk2}]

    global_block_count = planning.choose_global_block_count(len(non_goalies))
    segments_meta, by_global = build_segment_timeline(global_block_count, match.game_minutes)
    T = len(segments_meta)

    model = cp_model.CpModel()

    # assign[(p,t,pos)] = 1 iff player p is in position pos in segment t.
    assign: dict[tuple[str, int, str], cp_model.IntVar] = {}
    on: dict[tuple[str, int], cp_model.IntVar] = {}

    for p in players:
        for t in range(T):
            on[(p, t)] = model.NewBoolVar(f"on_{p}_{t}")
            for pos in ALL_POSITIONS:
                assign[(p, t, pos)] = model.NewBoolVar(f"a_{p}_{t}_{pos}")

    # Exactly one player per position per segment.
    for t in range(T):
        for pos in ALL_POSITIONS:
            model.Add(sum(assign[(p, t, pos)] for p in players) == 1)

    # Player on-field linkage.
    for p in players:
        for t in range(T):
            model.Add(sum(assign[(p, t, pos)] for pos in ALL_POSITIONS) == on[(p, t)])

    # Exactly 7 players on field.
    for t in range(T):
        model.Add(sum(on[(p, t)] for p in players) == 7)

    # GK constraints + both goalies always on field.
    for t, seg in enumerate(segments_meta):
        if seg["half"] == 1:
            model.Add(assign[(gk1, t, "GK")] == 1)
            model.Add(assign[(gk2, t, "GK")] == 0)
        else:
            model.Add(assign[(gk2, t, "GK")] == 1)
            model.Add(assign[(gk1, t, "GK")] == 0)

        model.Add(on[(gk1, t)] == 1)
        model.Add(on[(gk2, t)] == 1)

    # Non-goalies never play GK.
    for p in non_goalies:
        for t in range(T):
            model.Add(assign[(p, t, "GK")] == 0)

    # Kickoff starters must be on in first segment.
    starters = set(match.kickoff_starters)
    for p in players:
        model.Add(on[(p, 0)] == (1 if p in starters else 0))

    # No substitutions inside a global block split across halftime.
    for g, idxs in by_global.items():
        if len(idxs) == 2:
            t1, t2 = idxs
            for p in non_goalies:
                model.Add(on[(p, t1)] == on[(p, t2)])
                for pos in OUTFIELD_POSITIONS:
                    model.Add(assign[(p, t1, pos)] == assign[(p, t2, pos)])

    # Representative on/off per global block.
    block_on: dict[tuple[str, int], cp_model.IntVar] = {}
    for p in players:
        for g in range(1, global_block_count + 1):
            t = by_global[g][0]
            block_on[(p, g)] = on[(p, t)]

    # Bench-stint guardrail: no long consecutive bench runs for non-goalies.
    if max_consecutive_bench_blocks >= 0:
        window = max_consecutive_bench_blocks + 1
        for p in non_goalies:
            for start_g in range(1, global_block_count - window + 2):
                window_on = [block_on[(p, g)] for g in range(start_g, start_g + window)]
                model.Add(sum(window_on) >= 1)

    # Objective pieces.
    terms = []

    # 1) Position changes (high priority): if player remains outfield in consecutive
    # segments but at different outfield position.
    for p in players:
        for t in range(T - 1):
            out_t = model.NewBoolVar(f"out_{p}_{t}")
            out_n = model.NewBoolVar(f"out_{p}_{t + 1}")
            model.Add(out_t == sum(assign[(p, t, pos)] for pos in OUTFIELD_POSITIONS))
            model.Add(out_n == sum(assign[(p, t + 1, pos)] for pos in OUTFIELD_POSITIONS))

            both_out = model.NewBoolVar(f"bothout_{p}_{t}")
            model.AddBoolAnd([out_t, out_n]).OnlyEnforceIf(both_out)
            model.AddBoolOr([out_t.Not(), out_n.Not()]).OnlyEnforceIf(both_out.Not())

            same_pos_vars = []
            for pos in OUTFIELD_POSITIONS:
                s = model.NewBoolVar(f"same_{p}_{t}_{pos}")
                model.Add(s <= assign[(p, t, pos)])
                model.Add(s <= assign[(p, t + 1, pos)])
                model.Add(s >= assign[(p, t, pos)] + assign[(p, t + 1, pos)] - 1)
                same_pos_vars.append(s)

            same_any = model.NewBoolVar(f"sameany_{p}_{t}")
            model.Add(same_any == sum(same_pos_vars))

            changed = model.NewBoolVar(f"chg_{p}_{t}")
            model.Add(changed >= both_out - same_any)
            model.Add(changed <= both_out)
            model.Add(changed <= 1 - same_any + (1 - both_out))
            terms.append(w_pos_change * changed)

    # 2) Sub toggles (medium): on/off changes between consecutive segments.
    for p in non_goalies:
        for t in range(T - 1):
            d = model.NewIntVar(0, 1, f"toggle_{p}_{t}")
            model.Add(d >= on[(p, t)] - on[(p, t + 1)])
            model.Add(d >= on[(p, t + 1)] - on[(p, t)])
            terms.append(w_sub_toggle * d)

    # 3) Fairness on global-block appearances for non-goalies.
    # Hard guardrail: each non-goalie must be within a small band.
    m = len(non_goalies)
    total_non_goalie_slots = 5 * global_block_count
    avg_num = total_non_goalie_slots
    avg_den = m
    floor_target = avg_num // avg_den
    ceil_target = (avg_num + avg_den - 1) // avg_den

    for p in non_goalies:
        block_plays = [block_on[(p, g)] for g in range(1, global_block_count + 1)]
        play_count = model.NewIntVar(0, global_block_count, f"plays_{p}")
        model.Add(play_count == sum(block_plays))

        # Bound play counts near average (default: floor/ceil targets, i.e. max gap <= 1 block).
        lower = max(0, floor_target - fairness_band_blocks)
        upper = min(global_block_count, ceil_target + fairness_band_blocks)
        model.Add(play_count >= lower)
        model.Add(play_count <= upper)

        # Keep a soft fairness term too, so solution is as balanced as possible
        # inside the allowed band.
        scaled = model.NewIntVar(-10000, 10000, f"scaled_{p}")
        model.Add(scaled == m * play_count - 5 * global_block_count)
        abs_scaled = model.NewIntVar(0, 10000, f"abs_scaled_{p}")
        model.AddAbsEquality(abs_scaled, scaled)
        terms.append(w_fairness * abs_scaled)

    # 4) Preference penalty (low).
    for p in players:
        for t in range(T):
            for pos in OUTFIELD_POSITIONS:
                penalty = planning.preference_penalty(p, pos, match.players)
                terms.append(w_pref * penalty * assign[(p, t, pos)])

    model.Minimize(sum(terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Solver could not find a feasible schedule")

    segments: list[SegmentPlan] = []
    for t, seg in enumerate(segments_meta):
        lineup: Dict[str, str] = {}
        for pos in ALL_POSITIONS:
            player = next(p for p in players if solver.Value(assign[(p, t, pos)]) == 1)
            lineup[pos] = player

        segments.append(
            SegmentPlan(
                half=seg["half"],
                half_segment_index=seg["half_segment_index"],
                global_block=seg["global_block"],
                start_min=seg["start_min"],
                end_min=seg["end_min"],
                lineup=lineup,
            )
        )

    return segments, global_block_count


def generate_solver(
    cfg: MatchConfig | dict[str, Any],
    open_images: bool = False,
    max_consecutive_bench_blocks: int = 1,
) -> Path:
    match = planning.ensure_match_config(cfg)

    out_dir = Path("output") / f"{match.game_id}_solver"
    out_dir.mkdir(parents=True, exist_ok=True)

    plan = planning.plan_match(
        match,
        strategy="solver",
        solver_adapter=build_schedule_solver,
        max_consecutive_bench_blocks=max_consecutive_bench_blocks,
    )

    publish_outputs(
        segments=plan.segments,
        cfg=match,
        global_block_count=plan.global_block_count,
        out_dir=out_dir,
        game_id=f"{match.game_id}_solver",
    )

    if open_images:
        open_images_in_order(out_dir)

    return out_dir
