#!/usr/bin/env python3
"""Legacy entrypoint for heuristic scheduler.

Use `uv run formation-graphics heuristic` for the new CLI.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from formation_graphics import core


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate 7v7 formation graphics and schedule")
    p.add_argument("--config", default=str(core.DEFAULT_LOCAL_CONFIG_PATH))
    p.add_argument("--open", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = core.load_game_config(Path(args.config))
    out = core.generate(cfg)
    print(f"Generated files in: {out}")
    if args.open:
        core.open_images_in_order(out)
