from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import planning, solver
from .config_model import MatchConfig
from .planning import ALL_POSITIONS, MatchPlan, SegmentPlan
from .publishing import compute_transition_markers


class SolveRequest(BaseModel):
    config: dict[str, Any]
    preset: str = "balanced"
    max_consecutive_bench: int | None = Field(default=None, ge=0)


app = FastAPI(title="Formation Graphics API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_BUILDER_PATH = PROJECT_ROOT / "config_builder.html"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(CONFIG_BUILDER_PATH)


@app.get("/config_builder.html")
def config_builder() -> FileResponse:
    return FileResponse(CONFIG_BUILDER_PATH)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/presets")
def presets() -> dict[str, dict[str, dict[str, int]]]:
    return {"presets": solver.SOLVER_PRESETS}


@app.post("/api/solve")
def solve(req: SolveRequest) -> dict[str, Any]:
    if req.preset not in solver.SOLVER_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown solver preset: {req.preset}")

    try:
        match = planning.ensure_match_config(req.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    solver_options = dict(solver.SOLVER_PRESETS[req.preset])
    if req.max_consecutive_bench is not None:
        solver_options["max_consecutive_bench_blocks"] = req.max_consecutive_bench
    solver_options.setdefault("max_consecutive_bench_blocks", 1)

    started = perf_counter()
    try:
        plan = planning.plan_match(
            match,
            strategy="solver",
            solver_adapter=solver.build_schedule_solver,
            **solver_options,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    elapsed = perf_counter() - started

    return serialize_solution(
        match,
        plan,
        req.preset,
        {
            "cached": False,
            "wall_time_seconds": round(elapsed, 4),
            "options": solver_options,
        },
    )


def serialize_solution(
    match: MatchConfig, plan: MatchPlan, preset: str, solver_meta: dict[str, Any]
) -> dict[str, Any]:
    all_players = list(match.players.keys())
    markers = compute_transition_markers(plan.segments)
    segments = [
        serialize_segment(segment, all_players, incoming, moved)
        for segment, (incoming, moved) in zip(plan.segments, markers)
    ]
    stats = compute_browser_stats(plan.segments, all_players)

    return {
        "game_id": match.game_id,
        "preset": preset,
        "solver": solver_meta,
        "global_block_count": plan.global_block_count,
        "segments": segments,
        "stats": stats,
        "summary": compute_summary(plan.segments, all_players),
    }


def serialize_segment(
    segment: SegmentPlan,
    all_players: list[str],
    incoming_players: set[str],
    moved_players: set[str],
) -> dict[str, Any]:
    on_field = set(segment.lineup.values())
    bench = [player for player in all_players if player not in on_field]
    return {
        "half": segment.half,
        "half_segment_index": segment.half_segment_index,
        "global_block": segment.global_block,
        "start_min": segment.start_min,
        "end_min": segment.end_min,
        "lineup": {position: segment.lineup[position] for position in ALL_POSITIONS},
        "bench": bench,
        "incoming_players": sorted(incoming_players),
        "moved_players": sorted(moved_players),
    }


def compute_browser_stats(
    segments: list[SegmentPlan], all_players: list[str]
) -> list[dict[str, Any]]:
    stats = []
    global_blocks = sorted({segment.global_block for segment in segments})

    for player in all_players:
        played_segments = 0
        benched_segments = 0
        total_minutes = 0.0
        bench_minutes = 0.0
        bench_runs: list[int] = []
        current_bench_run = 0

        for segment in segments:
            duration = segment.end_min - segment.start_min
            on_field = player in segment.lineup.values()
            if on_field:
                played_segments += 1
                total_minutes += duration
            else:
                benched_segments += 1
                bench_minutes += duration

        for global_block in global_blocks:
            block_segments = [s for s in segments if s.global_block == global_block]
            on_field_in_block = any(player in segment.lineup.values() for segment in block_segments)
            if on_field_in_block:
                if current_bench_run:
                    bench_runs.append(current_bench_run)
                    current_bench_run = 0
            else:
                current_bench_run += 1

        if current_bench_run:
            bench_runs.append(current_bench_run)

        stats.append(
            {
                "player": player,
                "played_segments": played_segments,
                "benched_segments": benched_segments,
                "total_minutes": round(total_minutes, 2),
                "bench_minutes": round(bench_minutes, 2),
                "max_bench_run_blocks": max(bench_runs, default=0),
            }
        )

    return stats


def compute_summary(segments: list[SegmentPlan], all_players: list[str]) -> dict[str, Any]:
    previous_on_field: set[str] | None = None
    substitution_events = 0
    total_on_off_toggles = 0

    for segment in segments:
        on_field = set(segment.lineup.values())
        if previous_on_field is not None:
            toggles = len(on_field.symmetric_difference(previous_on_field))
            total_on_off_toggles += toggles
            if toggles:
                substitution_events += 1
        previous_on_field = on_field

    max_bench_run = max(
        (stat["max_bench_run_blocks"] for stat in compute_browser_stats(segments, all_players)),
        default=0,
    )

    return {
        "segment_count": len(segments),
        "substitution_events": substitution_events,
        "total_on_off_toggles": total_on_off_toggles,
        "max_bench_run_blocks": max_bench_run,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("formation_graphics.web:app", host="127.0.0.1", port=8000, reload=True)
