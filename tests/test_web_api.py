from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class WebApiTests(unittest.TestCase):
    def test_serves_config_builder_ui(self) -> None:
        from formation_graphics.web import app

        client = TestClient(app)
        response = client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn("Formation Graphics Config Builder", response.text)
        self.assertIn("Solver preview", response.text)

    def test_presets_endpoint_lists_solver_presets(self) -> None:
        from formation_graphics.web import app

        client = TestClient(app)
        response = client.get("/api/presets")

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIn("balanced", body["presets"])
        self.assertIn("five-minute", body["presets"])
        self.assertIn("steady", body["presets"])
        self.assertIn("compromise", body["presets"])
        self.assertIn("low-chaos", body["presets"])
        self.assertEqual(8, body["presets"]["five-minute"]["global_block_count"])

    def test_solve_endpoint_returns_serialized_plan(self) -> None:
        from formation_graphics import planning
        from formation_graphics.web import app

        client = TestClient(app)
        cfg = {
            "game_id": "web_api",
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
        plan = planning.MatchPlan(segments=segments, global_block_count=global_block_count)

        with patch(
            "formation_graphics.web.planning.plan_match", return_value=plan
        ) as plan_match_mock:
            response = client.post("/api/solve", json={"config": cfg, "preset": "five-minute"})

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("web_api", body["game_id"])
        self.assertEqual("five-minute", body["preset"])
        self.assertEqual(global_block_count, body["global_block_count"])
        self.assertFalse(body["solver"]["cached"])
        self.assertGreaterEqual(body["solver"]["wall_time_seconds"], 0)
        self.assertEqual(8, body["solver"]["options"]["global_block_count"])
        self.assertEqual(len(segments), len(body["segments"]))
        self.assertIn("bench", body["segments"][0])
        self.assertIn("incoming_players", body["segments"][0])
        self.assertIn("moved_players", body["segments"][0])
        self.assertEqual([], body["segments"][0]["incoming_players"])
        self.assertIn("total_minutes", body["stats"][0])
        self.assertIn("bench_minutes", body["stats"][0])
        self.assertIn("summary", body)

        kwargs = plan_match_mock.call_args.kwargs
        self.assertEqual("solver", kwargs["strategy"])
        self.assertEqual(8, kwargs["global_block_count"])

    def test_solve_endpoint_rejects_unknown_preset(self) -> None:
        from formation_graphics.web import app

        client = TestClient(app)
        response = client.post("/api/solve", json={"config": {}, "preset": "does-not-exist"})

        self.assertEqual(400, response.status_code)


if __name__ == "__main__":
    unittest.main()
