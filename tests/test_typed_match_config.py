from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class TypedMatchConfigTests(unittest.TestCase):
    def test_load_game_config_returns_typed_match_config(self) -> None:
        from formation_graphics.config_model import MatchConfig
        from formation_graphics.planning import load_game_config

        raw = {
            "game_id": "typed_test",
            "game_minutes": 40,
            "players": {
                "P1": {"positions": ["CM", "LM", "RM"]},
                "P2": {"positions": ["LB", "RB", "CM"]},
                "P3": {"positions": ["ST", "CM", "RM"]},
                "P4": {"positions": ["RB", "LB", "RM"]},
                "P5": {"positions": ["LM", "CM", "RM"]},
                "P6": {"positions": ["ST", "RM", "CM"]},
                "P7": {"positions": ["CM", "LB", "RB"]},
            },
            "gk1": "P1",
            "gk2": "P6",
            "kickoff_starters": ["P1", "P2", "P3", "P4", "P5", "P6", "P7"],
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "game.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            cfg = load_game_config(path)

        self.assertIsInstance(cfg, MatchConfig)
        self.assertEqual(cfg.game_id, "typed_test")
        self.assertEqual(cfg.players["P1"].positions[0], "CM")


if __name__ == "__main__":
    unittest.main()
