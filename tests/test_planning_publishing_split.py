from __future__ import annotations

import csv
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

    def test_schedule_csv_uses_configured_halftime_for_half_relative_minutes(self) -> None:
        from formation_graphics import planning, publishing

        cfg = {
            "game_id": "sixty_minute_match",
            "game_minutes": 60,
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

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schedule.csv"
            publishing.write_schedule_csv(segments, list(cfg["players"].keys()), path)

            rows = list(csv.DictReader(path.open(encoding="utf-8")))

        first_half2 = next(row for row in rows if row["half"] == "2")
        self.assertEqual(first_half2["start_min"], "30.00")
        self.assertEqual(first_half2["half_start_min"], "0.00")


if __name__ == "__main__":
    unittest.main()
