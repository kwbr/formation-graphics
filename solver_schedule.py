#!/usr/bin/env python3
"""Legacy entrypoint for solver scheduler.

Use `uv run formation-graphics solver` for the new CLI.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from formation_graphics import core, solver


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate solver-optimized 7v7 schedule")
    p.add_argument("--config", default=str(core.DEFAULT_LOCAL_CONFIG_PATH))
    p.add_argument("--open", action="store_true")
    p.add_argument("--max-consecutive-bench", type=int, default=1)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = core.load_game_config(Path(args.config))
    out = solver.generate_solver(
        cfg,
        open_images=args.open,
        max_consecutive_bench_blocks=args.max_consecutive_bench,
    )
    print(f"Generated solver files in: {out}")
