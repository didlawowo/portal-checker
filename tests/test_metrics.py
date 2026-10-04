"""Metrics contracts: cache-only reads, bounded labels and deterministic groups."""

import asyncio
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import api
from src.metrics import classify_status, render_metrics

NOW = 1791072000
UPDATED = datetime.fromtimestamp(NOW, timezone.utc)


def endpoint(path="/", **extra):
    return dict(
        url="https://app.example.com" + path,
        namespace="apps",
        name="app",
        type="ingress",
        **extra,
    )


def samples(text, name):
    prefix = "portal_checker_" + name
    return [
        (line.rsplit(" ", 1)[0], float(line.rsplit(" ", 1)[1]))
        for line in text.splitlines()
        if line.startswith(prefix + "{") or line.startswith(prefix + " ")
    ]


def value(text, name):
    values = samples(text, name)
    assert len(values) == 1
    return values[0][1]


def active_state(text, name):
    return [
        re.search(r'state="([^"]+)"', labels).group(1)
        for labels, val in samples(text, name)
        if val == 1
    ]


def render(rows, **kwargs):
    return render_metrics(
        {"results": rows, "last_updated": UPDATED, **kwargs}, 300, now=NOW
    )


@pytest.mark.parametrize(
    "status,state",
    [
        (200, "healthy"),
        (204, "healthy"),
        (299, "healthy"),
        (301, "healthy"),
        (399, "healthy"),
        (401, "warning"),
        (403, "warning"),
        (405, "warning"),
        (429, "warning"),
        (404, "failed"),
        (408, "failed"),
        (495, "failed"),
        (500, "failed"),
        (503, "failed"),
        (0, "failed"),
        (None, "unknown"),
        ("200", "unknown"),
    ],
)
def test_http_classification(status, state):
    assert classify_status(status) == state


def test_duplicate_paths_worst_status_max_latency_and_min_tls_expiry():
    rows = [
        endpoint(
            "/a?token=secret",
            status=200,
            response_time=10,
            ssl_info={"expiry_date": "2026-11-01T00:00:00"},
        ),
        endpoint(
            "/b",
            status=503,
            response_time=2500,
            ssl_info={"expiry_date": "2026-10-01T00:00:00+00:00"},
        ),
    ]
    text = render(rows)
    assert text == render(list(reversed(rows)))
    assert active_state(text, "endpoint_state") == ["failed"]
    assert value(text, "endpoint_up") == 0
    assert value(text, "endpoint_response_time_seconds") == 2.5
    assert value(text, "endpoint_last_check_timestamp_seconds") == NOW
    assert (
        value(text, "endpoint_tls_expiry_timestamp_seconds")
        == datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()
    )
    assert value(text, "endpoint_tls_expiry_timestamp_seconds") < NOW
    assert "secret" not in text and "/a" not in text
    identities = [
        line.rsplit(" ", 1)[0] for line in text.splitlines() if not line.startswith("#")
    ]
    assert len(identities) == len(set(identities))


def test_duplicate_exact_urls_remain_order_independent():
    rows = [
        endpoint(status=200, response_time=20),
        endpoint(status=503, response_time=40),
    ]
    assert render(rows) == render(list(reversed(rows)))
    assert value(render(rows), "endpoint_up") == 0
    assert value(render(rows), "endpoint_response_time_seconds") == 0.04


def test_empty_inventory_and_removed_resources():
    text = render([])
    assert len(samples(text, "endpoints")) == 4
    assert all(val == 0 for _, val in samples(text, "endpoints"))
    assert not samples(text, "endpoint_state")
    assert not samples(render([endpoint(status=200)], discovered=[]), "endpoint_state")


def test_pending_and_partial_groups_are_unknown():
    for rows in ([], [endpoint("/a", status=200)]):
        text = render(rows, discovered=[endpoint("/a"), endpoint("/b")])
        assert active_state(text, "endpoint_state") == ["unknown"]
        assert value(text, "endpoint_tested") == 0
        assert value(text, "endpoint_last_check_timestamp_seconds") == 0
        assert value(text, "endpoint_stale") == 0
        assert not samples(text, "endpoint_up")
        assert not samples(text, "endpoint_response_time_seconds")
        assert active_state(text, "endpoint_tls_state") == ["unknown"]


def test_stale_preserves_last_result_and_precise_timestamp():
    text = render(
        [endpoint(status=401)],
        last_updated=datetime.fromtimestamp(NOW - 301, timezone.utc),
    )
    assert value(text, "endpoint_stale") == 1
    assert value(text, "endpoint_last_check_timestamp_seconds") == NOW - 301
    assert active_state(text, "endpoint_state") == ["warning"]
    assert value(text, "endpoint_up") == 1


@pytest.mark.parametrize(
    "ssl_info", [None, {}, {"expiry_date": "bad"}, {"days_remaining": 20}]
)
def test_unknown_tls_is_not_expired_or_http_only(ssl_info):
    text = render([endpoint(status=495, ssl_info=ssl_info)])
    assert active_state(text, "endpoint_tls_state") == ["unknown"]
    assert not samples(text, "endpoint_tls_expiry_timestamp_seconds")


def test_partial_tls_is_unknown_and_http_only_is_explicit():
    rows = [
        endpoint("/a", status=200, ssl_info={"expiry_date": "2026-11-01"}),
        endpoint("/b", status=200),
    ]
    assert active_state(render(rows), "endpoint_tls_state") == ["unknown"]
    assert not samples(render(rows), "endpoint_tls_expiry_timestamp_seconds")
    rows[0]["url"] = "http://app.example.com/a"
    assert active_state(render(rows[:1]), "endpoint_tls_state") == ["http_only"]


def test_labels_exclude_credentials_queries_metadata_and_invalid_names():
    row = endpoint(
        status=200,
        annotations={"token": "SECRET"},
        details="SECRET",
        labels={"email": "PII"},
    )
    row.update(
        url="https://user:SECRET@app.example.com/private/PII?token=SECRET#PII",
        namespace='bad"SECRET\n',
        name="PII@example.com",
        type="SECRET",
    )
    text = render([row])
    assert 'host="app.example.com"' in text
    assert 'namespace="unknown"' in text
    assert all(secret not in text for secret in ("SECRET", "PII", "private", "user:"))
    row["url"] = "https://[broken"
    assert 'host="unknown"' in render([row])


@pytest.mark.parametrize("response_time", [None, -1, float("nan"), float("inf"), "20"])
def test_invalid_latency_is_absent(response_time):
    assert not samples(
        render([endpoint(status=200, response_time=response_time)]),
        "endpoint_response_time_seconds",
    )


@pytest.fixture
def cache(monkeypatch):
    cache = {"results": [], "last_updated": None}
    monkeypatch.setattr(api, "_test_results_cache", cache)
    return cache


def test_scrape_never_calls_network_discovery_file_loader_or_refresh(
    monkeypatch, cache
):
    for name in (
        "get_all_urls_with_details",
        "load_urls_from_file",
        "check_urls_async",
        "_trigger_async_refresh",
    ):
        monkeypatch.setattr(
            api, name, Mock(side_effect=AssertionError("scrape performed work"))
        )
    cache.update(results=[endpoint(status=200, response_time=20)], last_updated=UPDATED)
    original = copy.deepcopy(cache)
    with api.app.test_client() as client:
        for _ in range(2):
            response = client.get("/metrics")
            assert response.status_code == 200
            assert response.content_type == "text/plain; version=0.0.4; charset=utf-8"
            assert value(response.text, "endpoint_up") == 1
    assert cache == original


@pytest.mark.asyncio
async def test_discovery_visible_before_check_then_new_results_replace_cache(
    monkeypatch, cache
):
    monkeypatch.setattr(api, "load_urls_from_file", lambda _: [endpoint()])
    monkeypatch.setattr(api, "_is_url_excluded_wrapper", lambda _: False)

    async def check(rows, update):
        assert active_state(render_metrics(cache, 300), "endpoint_state") == ["unknown"]
        rows[0].update(status=200, response_time=12)
        assert "status" not in cache["discovered"][0]
        return rows

    monkeypatch.setattr(api, "check_urls_async", check)
    await api._run_url_tests()
    assert active_state(render_metrics(cache, 300), "endpoint_state") == ["healthy"]
    assert cache["last_updated"].tzinfo == timezone.utc
    cache["results"][0]["status"] = 503
    assert value(render_metrics(cache, 300), "endpoint_up") == 0


@pytest.mark.asyncio
async def test_older_concurrent_pass_cannot_overwrite_newer_results(monkeypatch, cache):
    monkeypatch.setattr(api, "load_urls_from_file", lambda _: [endpoint()])
    monkeypatch.setattr(api, "_is_url_excluded_wrapper", lambda _: False)
    entered, release = asyncio.Event(), asyncio.Event()

    async def check(rows, update):
        if not entered.is_set():
            entered.set()
            await release.wait()
            rows[0]["status"] = 503
        else:
            rows[0]["status"] = 200
        return rows

    monkeypatch.setattr(api, "check_urls_async", check)
    older = asyncio.create_task(api._run_url_tests())
    await entered.wait()
    await api._run_url_tests()
    release.set()
    await older
    assert cache["results"][0]["status"] == 200


def test_dashboard_uses_only_exported_metrics_and_configurable_datasource():
    dashboard = json.loads(
        (
            Path(__file__).resolve().parents[1] / "grafana/portal-checker.json"
        ).read_text()
    )
    variables = {v["name"]: v for v in dashboard["templating"]["list"]}
    assert variables["datasource"]["type"] == "datasource"
    assert variables["datasource"]["query"] == "prometheus"
    from src.metrics import HELP

    for panel in dashboard["panels"]:
        assert panel["datasource"]["uid"] == "${datasource}"
        for target in panel["targets"]:
            assert set(re.findall(r"portal_checker_(\w+)", target["expr"])) <= set(HELP)
            assert 'instance=~"$instance"' in target["expr"]
