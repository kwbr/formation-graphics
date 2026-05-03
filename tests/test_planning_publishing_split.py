from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class PlanningPublishingSplitTests(unittest.TestCase):
    def test_planning_module_builds_schedule_without_rendering(self) -> None:
        from formation_graphics import planning

        cfg = {
            "game_id": "tdd_plan",
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

        planning.validate_config(cfg)
        segments, global_block_count = planning.build_schedule(cfg)

        self.assertGreater(len(segments), 0)
        self.assertGreaterEqual(global_block_count, 1)
        self.assertEqual({1, 2}, {s.half for s in segments})

    def test_publishing_module_writes_outputs_from_plan(self) -> None:
        from formation_graphics import planning, publishing

        cfg = {
            "game_id": "tdd_publish",
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

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / cfg["game_id"]
            out_dir.mkdir(parents=True, exist_ok=True)
            publishing.publish_outputs(
                segments=segments,
                cfg=cfg,
                global_block_count=global_block_count,
                out_dir=out_dir,
                game_id=cfg["game_id"],
            )

            self.assertTrue((out_dir / "schedule.csv").exists())
            self.assertTrue((out_dir / "player_stats.csv").exists())
            self.assertTrue((out_dir / "summary.txt").exists())
            self.assertTrue((out_dir / "half1_sheet_a4.pdf").exists())
            self.assertTrue((out_dir / "half2_sheet_a4.pdf").exists())


if __name__ == "__main__":
    unittest.main()
