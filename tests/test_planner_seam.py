from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PlannerSeamTests(unittest.TestCase):
    def test_plan_match_returns_match_plan_for_heuristic_strategy(self) -> None:
        from formation_graphics import planning

        cfg = {
            "game_id": "planner_seam",
            "game_minutes": 40,
            "players": {
                "P1": {"positions": ["CM", "LM", "RM"]},
                "P2": {"positions": ["LB", "RB", "CM"]},
                "P3": {"positions": ["ST", "CM", "RM"]},
                "P4": {"positions": ["RB", "LB", "RM"]},
                "P5": {"positions": ["LM", "CM", "RM"]},
                "P6": {"positions": ["ST", "RM", "CM"]},
                "P7": {"positions": ["CM", "LB", "RB"]},
                "P8": {"positions": ["RM", "LM", "ST"]},
            },
            "gk1": "P1",
            "gk2": "P6",
            "kickoff_starters": ["P1", "P2", "P3", "P4", "P5", "P6", "P7"],
        }

        plan = planning.plan_match(cfg, strategy="heuristic")

        self.assertGreater(len(plan.segments), 0)
        self.assertGreaterEqual(plan.global_block_count, 1)

    def test_solver_generate_uses_plan_match_with_solver_strategy(self) -> None:
        from formation_graphics import planning, solver

        cfg = {
            "game_id": "planner_solver",
            "game_minutes": 40,
            "players": {
                "P1": {"positions": ["CM", "LM", "RM"]},
                "P2": {"positions": ["LB", "RB", "CM"]},
                "P3": {"positions": ["ST", "CM", "RM"]},
                "P4": {"positions": ["RB", "LB", "RM"]},
                "P5": {"positions": ["LM", "CM", "RM"]},
                "P6": {"positions": ["ST", "RM", "CM"]},
                "P7": {"positions": ["CM", "LB", "RB"]},
                "P8": {"positions": ["RM", "LM", "ST"]},
            },
            "gk1": "P1",
            "gk2": "P6",
            "kickoff_starters": ["P1", "P2", "P3", "P4", "P5", "P6", "P7"],
        }

        segments, global_block_count = planning.build_schedule(cfg)
        fake_plan = planning.MatchPlan(segments=segments, global_block_count=global_block_count)

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            with patch("formation_graphics.solver.Path", return_value=output_root), patch(
                "formation_graphics.solver.planning.plan_match",
                return_value=fake_plan,
            ) as plan_match_mock, patch("formation_graphics.solver.base.publish_outputs"):
                solver.generate_solver(cfg)

                plan_match_mock.assert_called_once()
                kwargs = plan_match_mock.call_args.kwargs
                self.assertEqual(kwargs["strategy"], "solver")


if __name__ == "__main__":
    unittest.main()
