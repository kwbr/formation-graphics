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

    def test_listed_positions_are_equal_preferences(self) -> None:
        from formation_graphics import planning
        from formation_graphics.config_model import PlayerConfig

        players_cfg = {"P1": PlayerConfig(positions=("RM", "LM", "CM"))}

        self.assertEqual(0, planning.preference_penalty("P1", "RM", players_cfg))
        self.assertEqual(0, planning.preference_penalty("P1", "LM", players_cfg))
        self.assertEqual(0, planning.preference_penalty("P1", "CM", players_cfg))
        self.assertGreater(
            planning.preference_penalty("P1", "ST", players_cfg),
            planning.preference_penalty("P1", "CM", players_cfg),
        )

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
            with (
                patch("formation_graphics.solver.Path", return_value=output_root),
                patch(
                    "formation_graphics.solver.planning.plan_match",
                    return_value=fake_plan,
                ) as plan_match_mock,
                patch("formation_graphics.solver.publish_outputs"),
            ):
                solver.generate_solver(cfg)

                plan_match_mock.assert_called_once()
                kwargs = plan_match_mock.call_args.kwargs
                self.assertEqual(kwargs["strategy"], "solver")
                self.assertEqual(kwargs["max_consecutive_bench_blocks"], 1)

    def test_solver_steady_and_compromise_presets_define_expected_block_counts(self) -> None:
        from formation_graphics import solver

        self.assertEqual(5, solver.SOLVER_PRESETS["steady"]["global_block_count"])
        self.assertEqual(6, solver.SOLVER_PRESETS["compromise"]["global_block_count"])
        self.assertEqual(1, solver.SOLVER_PRESETS["steady"]["max_consecutive_bench_blocks"])
        self.assertEqual(1, solver.SOLVER_PRESETS["compromise"]["max_consecutive_bench_blocks"])

    def test_solver_five_minute_preset_passes_eight_global_blocks(self) -> None:
        from formation_graphics import planning, solver

        cfg = {
            "game_id": "five_minute_solver",
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

        segments, _global_block_count = planning.build_schedule(cfg)
        fake_plan = planning.MatchPlan(segments=segments, global_block_count=8)

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            with (
                patch("formation_graphics.solver.Path", return_value=output_root),
                patch(
                    "formation_graphics.solver.planning.plan_match",
                    return_value=fake_plan,
                ) as plan_match_mock,
                patch("formation_graphics.solver.publish_outputs"),
            ):
                out_dir = solver.generate_solver(cfg, preset="five-minute")

                self.assertTrue(str(out_dir).endswith("five_minute_solver_solver_five_minute"))
                kwargs = plan_match_mock.call_args.kwargs
                self.assertEqual(kwargs["global_block_count"], 8)
                self.assertEqual(kwargs["max_consecutive_bench_blocks"], 1)

    def test_solver_low_chaos_preset_passes_low_chaos_options(self) -> None:
        from formation_graphics import planning, solver

        cfg = {
            "game_id": "low_chaos_solver",
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

        segments, _global_block_count = planning.build_schedule(cfg)
        fake_plan = planning.MatchPlan(segments=segments, global_block_count=4)

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            with (
                patch("formation_graphics.solver.Path", return_value=output_root),
                patch(
                    "formation_graphics.solver.planning.plan_match",
                    return_value=fake_plan,
                ) as plan_match_mock,
                patch("formation_graphics.solver.publish_outputs"),
            ):
                out_dir = solver.generate_solver(cfg, preset="low-chaos")

                self.assertTrue(str(out_dir).endswith("low_chaos_solver_solver_low_chaos"))
                kwargs = plan_match_mock.call_args.kwargs
                self.assertEqual(kwargs["global_block_count"], 4)
                self.assertEqual(kwargs["fairness_band_blocks"], 2)
                self.assertEqual(kwargs["max_consecutive_bench_blocks"], 1)
                self.assertGreater(kwargs["w_sub_toggle"], 100)


if __name__ == "__main__":
    unittest.main()
