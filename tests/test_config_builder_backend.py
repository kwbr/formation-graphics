from __future__ import annotations

import contextlib
import http.server
import json
import socket
import socketserver
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Route, sync_playwright


class QuietHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def site_url() -> Iterator[str]:
    repo_root = Path(__file__).resolve().parents[1]
    port = free_port()

    handler = lambda *args, **kwargs: QuietHttpRequestHandler(  # noqa: E731
        *args,
        directory=str(repo_root),
        **kwargs,
    )
    server = socketserver.TCPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def page() -> Iterator[Page]:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            yield page
            browser.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright Chromium is not installed or not launchable: {exc}")


def test_config_builder_loads_presets_and_solves_with_backend(page: Page, site_url: str) -> None:
    def fulfill_presets(route: Route) -> None:
        route.fulfill(
            json={
                "presets": {
                    "balanced": {},
                    "compromise": {"global_block_count": 6},
                    "five-minute": {"global_block_count": 8},
                }
            }
        )

    def fulfill_solve(route: Route) -> None:
        request = json.loads(route.request.post_data or "{}")
        assert request["preset"] == "compromise"
        assert request["max_consecutive_bench"] == 2
        assert request["config"]["game_id"] == "game9"
        route.fulfill(
            json={
                "game_id": "game9",
                "preset": "compromise",
                "global_block_count": 6,
                "solver": {
                    "cached": False,
                    "wall_time_seconds": 0.1234,
                    "options": {"global_block_count": 6, "max_consecutive_bench_blocks": 2},
                },
                "segments": [
                    {
                        "half": 1,
                        "half_segment_index": 1,
                        "global_block": 1,
                        "start_min": 0.0,
                        "end_min": 6.67,
                        "lineup": {
                            "GK": "Cali",
                            "LB": "Philippa",
                            "RB": "Poppy",
                            "LM": "Matilda",
                            "CM": "Maia",
                            "RM": "Juna",
                            "ST": "Leni",
                        },
                        "bench": ["Annabelle", "Ellie", "Livvy", "Myla"],
                        "incoming_players": ["Philippa"],
                        "moved_players": ["Poppy"],
                    }
                ],
                "stats": [
                    {
                        "player": "Cali",
                        "played_segments": 1,
                        "benched_segments": 0,
                        "total_minutes": 6.67,
                        "bench_minutes": 0.0,
                        "max_bench_run_blocks": 0,
                    }
                ],
                "summary": {
                    "segment_count": 1,
                    "substitution_events": 0,
                    "total_on_off_toggles": 0,
                    "max_bench_run_blocks": 0,
                },
            }
        )

    page.route("**/api/presets", fulfill_presets)
    page.route("**/api/solve", fulfill_solve)
    page.goto(f"{site_url}/config_builder.html", wait_until="domcontentloaded")

    page.locator("#loadPresets").click()
    page.locator("#solverStatus").get_by_text("Loaded 3 presets.").wait_for()
    page.locator("#solverPreset").select_option("compromise")
    page.locator("#maxConsecutiveBench").fill("2")

    page.locator("#solveBackend").click()
    page.locator("#solverStatus").get_by_text("Solved game9 with compromise").wait_for()

    assert "Annabelle, Ellie, Livvy, Myla" in page.locator("#solverPreview").inner_text()
    assert "Global blocks: 6" in page.locator("#solverPreview").inner_text()
    assert "Max consecutive bench option: 2" in page.locator("#solverPreview").inner_text()
    assert "Solver time: 0.1234s" in page.locator("#solverPreview").inner_text()
    assert "Cached: no" in page.locator("#solverPreview").inner_text()
    assert "Coming on: Philippa" in page.locator("#solverPreview").inner_text()
    assert "Position changes: Poppy" in page.locator("#solverPreview").inner_text()
    assert "Playing time" in page.locator("#solverPreview").inner_text()
    assert "6.67 min" in page.locator("#solverPreview").inner_text()
    assert page.locator("#printHalfSheets").is_enabled()
    assert page.locator(".print-half-sheet").count() == 1
    assert page.locator(".print-sheet-table").count() == 1
    assert page.locator(".print-pitch-card").count() == 1
    assert "↑ coming on · ↔ position change" in page.locator(".print-half-sheet").inner_text()
    assert page.locator(".solution-card").count() >= 1
    assert (
        "Cali"
        in page.locator(
            "#solverPreview > .solution-segments .solution-pos[data-pos='GK']"
        ).inner_text()
    )
    assert page.locator("#solverPreview > .solution-segments .solution-pos.incoming").count() == 1
    assert page.locator("#solverPreview > .solution-segments .solution-pos.moved").count() == 1
