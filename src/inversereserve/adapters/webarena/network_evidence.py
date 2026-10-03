"""Network evidence redaction, independent of browser and container lifecycle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

SENSITIVE_HAR_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
        "x-m2-admin-auto-login",
        "x-m2-customer-auto-login",
        "x-postmill-auto-login",
    }
)


def _filtered_headers(rows: object) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(rows, list):
        return ([], 0)
    kept = []
    removed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("name", "")).casefold() in SENSITIVE_HAR_HEADERS:
            removed += 1
        else:
            kept.append(row)
    return (kept, removed)


def _redact_forbidden_values(value: Any, secrets: tuple[str, ...]) -> tuple[Any, int]:
    if isinstance(value, dict):
        output = {}
        count = 0
        for key, item in value.items():
            cleaned, observed = _redact_forbidden_values(item, secrets)
            output[key] = cleaned
            count += observed
        return (output, count)
    if isinstance(value, list):
        output = []
        count = 0
        for item in value:
            cleaned, observed = _redact_forbidden_values(item, secrets)
            output.append(cleaned)
            count += observed
        return (output, count)
    if isinstance(value, str):
        cleaned = value
        count = 0
        for secret in secrets:
            observed = cleaned.count(secret)
            if observed:
                cleaned = cleaned.replace(secret, "<redacted-harness-credential>")
                count += observed
        return (cleaned, count)
    return (value, 0)


def sanitize_network_har_v1(path: Path, *, forbidden_values: Iterable[str]) -> dict[str, Any]:
    """Remove authentication material without changing evaluator payloads."""
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    log = raw.get("log")
    if not isinstance(log, dict) or not isinstance(log.get("entries"), list):
        raise ValueError("network HAR has no standard log entries")
    removed_headers = 0
    removed_cookies = 0
    for entry in log["entries"]:
        if not isinstance(entry, dict):
            continue
        for side in ("request", "response"):
            message = entry.get(side)
            if not isinstance(message, dict):
                continue
            headers, count = _filtered_headers(message.get("headers"))
            message["headers"] = headers
            removed_headers += count
            cookies = message.get("cookies")
            if isinstance(cookies, list):
                removed_cookies += len(cookies)
                message["cookies"] = []
    secrets = tuple(sorted({str(value) for value in forbidden_values if str(value)}, key=len, reverse=True))
    raw, redacted_strings = _redact_forbidden_values(raw, secrets)
    serialized = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if any((secret in serialized for secret in secrets)):
        raise RuntimeError("credential material remains after HAR sanitization")
    temporary = path.with_suffix(path.suffix + ".sanitized.tmp")
    temporary.write_text(serialized + "\n", encoding="utf-8")
    temporary.replace(path)
    return {
        "entries": len(log["entries"]),
        "removed_sensitive_headers": removed_headers,
        "removed_cookie_records": removed_cookies,
        "redacted_credential_strings": redacted_strings,
        "credential_material_remaining": False,
        "noncredential_post_data_preserved": True,
    }
