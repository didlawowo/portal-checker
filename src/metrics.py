"""Read-only Prometheus text exposition of the existing check cache.

Each family has a fixed label schema; paths and arbitrary metadata never become
labels. No persistent registry retains series for resources that disappear.
"""

import math
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlsplit

LABELS = ("namespace", "resource", "resource_type", "host")
STATES = ("healthy", "warning", "failed", "unknown")
HELP = {
    "endpoints": "Current resource-host groups by check state.",
    "endpoint_state": "One-hot state of each resource-host group.",
    "endpoint_up": "1 for healthy or warning; 0 for failed. Absent if untested.",
    "endpoint_tested": "1 when every path in the group has a cached check.",
    "endpoint_last_check_timestamp_seconds": "Oldest check in the group; 0 if untested.",
    "endpoint_stale": "1 when a tested group is older than the configured cache TTL.",
    "endpoint_response_time_seconds": "Maximum cached response time across paths.",
    "endpoint_tls_state": "One-hot TLS state: known, unknown or http_only.",
    "endpoint_tls_expiry_timestamp_seconds": "Earliest TLS expiry; absent if TLS is unknown or HTTP only.",
}


def _name(value, limit=253):
    """Accept only Kubernetes/DNS identifiers, never free-form metadata."""
    value = str(value or "")
    return (
        value
        if len(value) <= limit
        and re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value)
        else "unknown"
    )


def _url(data):
    value = str(data.get("url", ""))
    try:
        return urlsplit(value if "://" in value else "https://" + value)
    except ValueError:
        return urlsplit("")


def _labels(data):
    return (
        _name(data.get("namespace"), 63),
        _name(data.get("name")),
        data.get("type") if data.get("type") in ("ingress", "httproute") else "unknown",
        _name(_url(data).hostname),
    )


def _identity(data):
    # The full URL is used only to join inventory and results in memory.
    return tuple(str(data.get(k, "")) for k in ("namespace", "name", "type", "url"))


def classify_status(status):
    """Classify the final HTTP response, including synthetic transport errors."""
    if not isinstance(status, int) or isinstance(status, bool):
        return "unknown"
    if 200 <= status < 400:
        return "healthy"
    if status in (401, 403, 405, 429):
        return "warning"
    return "failed"


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _expiry(result):
    info = result.get("ssl_info") or {}
    try:
        expiry = datetime.fromisoformat(info["expiry_date"])
        # get_ssl_cert_info parses a GMT certificate date into a naive datetime.
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry.timestamp()
    except (KeyError, ValueError, TypeError, OverflowError):
        return None


def render_metrics(snapshot, ttl, now=None):
    """Render a stable snapshot; missing data never masquerades as success."""
    now = time.time() if now is None else now
    families = {name: [] for name in HELP}

    def emit(name, value, labels=()):
        suffix = ""
        if labels:
            # Values are allowlisted above; escaping also protects future labels.
            def escape(value):
                return (
                    str(value)
                    .replace("\\", "\\\\")
                    .replace("\n", "\\n")
                    .replace('"', '\\"')
                )

            suffix = "{" + ",".join(f'{k}="{escape(v)}"' for k, v in labels) + "}"
        families[name].append(f"portal_checker_{name}{suffix} {value:.17g}")

    results = defaultdict(list)
    for row in snapshot.get("results", []):
        results[_identity(row)].append(row)
    inventory = snapshot.get("discovered", snapshot.get("results", []))
    groups = defaultdict(dict)
    for row in inventory:
        groups[_labels(row)][_identity(row)] = row
    updated = snapshot.get("last_updated")
    checked_at = updated.timestamp() if isinstance(updated, datetime) else 0
    counts = dict.fromkeys(STATES, 0)
    for key, paths in sorted(groups.items()):
        labels = tuple(zip(LABELS, key))
        rows = [row for identity in paths for row in results.get(identity, [{}])]
        states = [classify_status(row.get("status")) for row in rows]
        tested = checked_at > 0 and "unknown" not in states
        state = max(states, key=lambda s: STATES.index(s)) if tested else "unknown"
        counts[state] += 1
        for candidate in STATES:
            emit(
                "endpoint_state",
                int(state == candidate),
                labels + (("state", candidate),),
            )
        emit("endpoint_tested", int(tested), labels)
        emit(
            "endpoint_last_check_timestamp_seconds", checked_at if tested else 0, labels
        )
        emit("endpoint_stale", int(tested and now - checked_at > ttl), labels)
        if tested:
            emit("endpoint_up", int(state != "failed"), labels)
            timings = [_number(row.get("response_time")) for row in rows]
            if all(value is not None and value >= 0 for value in timings):
                emit("endpoint_response_time_seconds", max(timings) / 1000, labels)

        tls_rows = [
            result
            for identity, row in paths.items()
            if _url(row).scheme != "http"
            for result in results.get(identity, [{}])
        ]
        expiries = [_expiry(row) for row in tls_rows]
        tls_state = "http_only" if not tls_rows else "unknown"
        if tls_rows and tested and all(value is not None for value in expiries):
            tls_state = "known"
            expiry = min(expiries)
            emit("endpoint_tls_expiry_timestamp_seconds", expiry, labels)
        for candidate in ("known", "unknown", "http_only"):
            emit(
                "endpoint_tls_state",
                int(tls_state == candidate),
                labels + (("state", candidate),),
            )

    for state, count in counts.items():
        emit("endpoints", count, (("state", state),))
    lines = []
    for name, samples in families.items():
        lines.extend(
            (
                f"# HELP portal_checker_{name} {HELP[name]}",
                f"# TYPE portal_checker_{name} gauge",
                *samples,
            )
        )
    return "\n".join(lines) + "\n"
