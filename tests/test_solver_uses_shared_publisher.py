from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SolverSharedPublisherTests(unittest.TestCase):
    def test_generate_solver_delegates_output_writes_to_shared_publisher(self) -> None:
        from formation_graphics import planning, solver

        cfg = {
            "game_id": "solver_publish_tdd",
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

        typed_cfg = planning.ensure_match_config(cfg)
        segments, global_block_count = planning.build_schedule(typed_cfg)

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            with patch("formation_graphics.solver.Path", return_value=output_root), patch(
                "formation_graphics.solver.build_schedule_solver",
                return_value=(segments, global_block_count),
            ), patch("formation_graphics.solver.base.publish_outputs") as publish_mock:
                solver.generate_solver(cfg)

                publish_mock.assert_called_once()
                kwargs = publish_mock.call_args.kwargs
                self.assertEqual(kwargs["segments"], segments)
                self.assertEqual(kwargs["cfg"], typed_cfg)
                self.assertEqual(kwargs["global_block_count"], global_block_count)
                self.assertTrue(str(kwargs["out_dir"]).endswith(f"{cfg['game_id']}_solver"))
                self.assertEqual(kwargs["game_id"], f"{cfg['game_id']}_solver")


if __name__ == "__main__":
    unittest.main()
