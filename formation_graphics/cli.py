from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from . import core, planning, solver
from .publishing import open_images_in_order


def cmd_init_config(args: argparse.Namespace) -> int:
    src = Path(args.example)
    dst = Path(args.output)

    if not src.exists():
        raise FileNotFoundError(f"Example config not found: {src}")

    if dst.exists() and not args.force:
        print(f"Config already exists: {dst} (use --force to overwrite)")
        return 1

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"Created config: {dst}")
    return 0


def cmd_heuristic(args: argparse.Namespace) -> int:
    cfg = planning.load_game_config(Path(args.config))
    out_dir = core.generate(cfg)
    print(f"Generated files in: {out_dir}")
    if args.open:
        open_images_in_order(out_dir)
    return 0


def cmd_solver(args: argparse.Namespace) -> int:
    cfg = planning.load_game_config(Path(args.config))
    out = solver.generate_solver(
        cfg,
        open_images=args.open,
        max_consecutive_bench_blocks=args.max_consecutive_bench,
        preset=args.preset,
    )
    print(f"Generated solver files in: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Formation graphics CLI")
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-config", help="Create local config from example template")
    p_init.add_argument("--example", default=str(planning.DEFAULT_EXAMPLE_CONFIG_PATH))
    p_init.add_argument("--output", default=str(planning.DEFAULT_LOCAL_CONFIG_PATH))
    p_init.add_argument("--force", action="store_true", help="Overwrite output config if it exists")
    p_init.set_defaults(func=cmd_init_config)

    p_heur = sub.add_parser("heuristic", help="Generate schedule with heuristic scheduler")
    p_heur.add_argument("--config", default=str(planning.DEFAULT_LOCAL_CONFIG_PATH))
    p_heur.add_argument("--open", action="store_true", help="Open generated segment images")
    p_heur.set_defaults(func=cmd_heuristic)

    p_solver = sub.add_parser("solver", help="Generate schedule with CP-SAT solver")
    p_solver.add_argument("--config", default=str(planning.DEFAULT_LOCAL_CONFIG_PATH))
    p_solver.add_argument("--open", action="store_true", help="Open generated segment images")
    p_solver.add_argument(
        "--preset",
        choices=sorted(solver.SOLVER_PRESETS),
        default="balanced",
        help="Solver preset: balanced keeps current behavior; low-chaos uses fewer, longer blocks",
    )
    p_solver.add_argument(
        "--max-consecutive-bench",
        type=int,
        default=None,
        help="Override max consecutive global blocks a non-goalie can be benched",
    )
    p_solver.set_defaults(func=cmd_solver)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
