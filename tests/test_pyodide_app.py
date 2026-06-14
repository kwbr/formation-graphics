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
from playwright.sync_api import Page, sync_playwright


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


def test_pyodide_app_runs_python_planner_in_browser(page: Page, site_url: str) -> None:
    page.goto(f"{site_url}/pyodide_test.html", wait_until="domcontentloaded")

    page.locator("#status[data-state='ready']").wait_for(timeout=90_000)
    page.locator("#runButton").click()
    page.locator("#output[data-state='done']").wait_for(timeout=30_000)

    output = json.loads(page.locator("#output").inner_text())

    assert output["status"] == "ok"
    assert output["source"] == "pyodide-python"
    assert output["game_id"] == "game9"
    assert output["global_block_count"] == 8
    assert output["segment_count"] == 8
    assert any(stat["player"] == "Cali" and stat["plays_whole_match"] for stat in output["stats"])


def test_pyodide_app_allows_changing_block_count(page: Page, site_url: str) -> None:
    page.goto(f"{site_url}/pyodide_test.html", wait_until="domcontentloaded")

    page.locator("#status[data-state='ready']").wait_for(timeout=90_000)
    page.locator("#blockCount").fill("6")
    page.locator("#runButton").click()
    page.locator("#output[data-state='done']").wait_for(timeout=30_000)

    output = json.loads(page.locator("#output").inner_text())

    assert output["global_block_count"] == 6
    assert output["segment_count"] == 6
