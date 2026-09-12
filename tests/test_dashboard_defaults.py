"""Regression tests for the dashboard defaults and controls."""

from __future__ import annotations

import os
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class _ControlParser(HTMLParser):
    """Collect dashboard controls without depending on attribute ordering."""

    def __init__(self) -> None:
        super().__init__()
        self.by_id: dict[str, dict[str, str | None]] = {}
        self.status_filters: set[str] = set()
        self.status_controls: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.by_id[element_id] = attributes
        status_filter = attributes.get("data-status-filter")
        if status_filter:
            self.status_filters.add(status_filter)
            self.status_controls[status_filter] = attributes


@pytest.fixture
def client():
    """Provide a Flask client and restore the process-wide toggle afterwards."""
    from src.api import _get_auto_refresh_state, _set_auto_refresh_state, app

    app.config["TESTING"] = True
    previous_state = _get_auto_refresh_state()["enabled"]
    with app.test_client() as test_client:
        yield test_client
    _set_auto_refresh_state(previous_state)


def test_auto_refresh_is_enabled_by_default_in_a_fresh_process():
    """The runtime toggle starts enabled without relying on a previous import."""
    environment = os.environ.copy()
    environment.pop("AUTO_REFRESH_ON_START", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.api import _get_auto_refresh_state; "
            "assert _get_auto_refresh_state()['enabled'] is True",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


def test_auto_refresh_endpoint_can_turn_off_and_on(client):
    """GET and POST expose and change the toggle, then the fixture restores it."""
    initial = client.get("/api/auto-refresh")
    assert initial.status_code == 200

    disabled = client.post("/api/auto-refresh", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.get_json()["enabled"] is False
    assert client.get("/api/auto-refresh").get_json()["enabled"] is False

    enabled = client.post("/api/auto-refresh", json={"enabled": True})
    assert enabled.status_code == 200
    assert enabled.get_json()["enabled"] is True
    assert client.get("/api/auto-refresh").get_json()["enabled"] is True


def test_dashboard_contains_accessible_filters_and_refresh_controls(client):
    """The rendered page keeps the controls required by the mobile dashboard."""
    response = client.get("/")
    assert response.status_code == 200
    parser = _ControlParser()
    parser.feed(response.get_data(as_text=True))

    assert parser.status_filters == {"all", "success", "client_errors", "server_errors"}
    assert all(
        "aria-pressed" in attributes for attributes in parser.status_controls.values()
    )

    clear_search = parser.by_id["clearSearchBtn"]
    assert clear_search["aria-label"] == "Effacer la recherche"
    assert "hidden" in clear_search
    assert "checked" in parser.by_id["autoRefreshToggle"]
    assert parser.by_id["mobileSort"]["id"] == "mobileSort"
    refresh_status = parser.by_id["refreshStatus"]
    assert refresh_status["role"] == "status"
    assert refresh_status["aria-live"] == "polite"
