"""Unit tests for core/har_parser.py — no network, no file I/O (except fixture HAR files)."""
from __future__ import annotations

import json
import sys
import pytest

from jac_loadtest.core.har_parser import parse_har
from tests.conftest import make_har


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_har(tmp_path, data: dict) -> str:
    p = tmp_path / "test.har"
    p.write_text(json.dumps(data))
    return str(p)


def _entry(method="POST", url="http://recorded-host:8000/walker/search",
           headers=None, mime="application/json", body=None, wait=42):
    return {
        "request": {
            "method": method,
            "url": url,
            "headers": headers or [],
            "postData": {"mimeType": "application/json", "text": body or "{}"},
            "queryString": [],
        },
        "response": {"status": 200, "content": {"mimeType": mime}},
        "timings": {"send": 1, "wait": wait, "receive": 5},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_minimal(tmp_path):
    har = make_har()
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://target:9000")
    assert len(entries) == 2
    assert entries[0].method == "POST"
    assert entries[0].url.startswith("http://target:9000")
    assert entries[0].think_time_ms == 50
    assert entries[1].think_time_ms == 42


@pytest.mark.unit
def test_mime_filter_default(tmp_path):
    har = make_har(entries=[
        _entry(url="http://h:8000/api/data", mime="application/json"),
        _entry(url="http://h:8000/img.png", mime="image/png"),
        _entry(url="http://h:8000/style.css", mime="text/css"),
        _entry(url="http://h:8000/font.woff2", mime="font/woff2"),
    ])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://target:9000")
    assert len(entries) == 1
    assert "/api/data" in entries[0].url


@pytest.mark.unit
def test_include_static_flag(tmp_path):
    har = make_har(entries=[
        _entry(url="http://h:8000/api", mime="application/json"),
        _entry(url="http://h:8000/img.png", mime="image/png"),
        _entry(url="http://h:8000/style.css", mime="text/css"),
    ])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://target:9000", include_static=True)
    assert len(entries) == 3


@pytest.mark.unit
def test_url_rewriting_origin(tmp_path):
    har = make_har(entries=[
        _entry(url="http://recorded-host:8000/walker/search?q=hello")
    ])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://staging.app.com:9000")
    assert entries[0].url == "http://staging.app.com:9000/walker/search?q=hello"


@pytest.mark.unit
def test_url_rewriting_port(tmp_path):
    har = make_har(entries=[
        _entry(url="http://localhost:8000/user/login")
    ])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://localhost:9999")
    assert entries[0].url.startswith("http://localhost:9999")
    assert "/user/login" in entries[0].url


@pytest.mark.unit
def test_header_sanitization(tmp_path):
    headers = [
        {"name": "Authorization", "value": "Bearer secret"},
        {"name": "Cookie", "value": "session=abc"},
        {"name": "Host", "value": "recorded-host:8000"},
        {"name": "Content-Length", "value": "42"},
        {"name": "Content-Type", "value": "application/json"},
        {"name": "X-Custom", "value": "keep-me"},
    ]
    har = make_har(entries=[_entry(headers=headers)])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://target:9000")
    hdrs = entries[0].headers
    assert "Authorization" not in hdrs
    assert "Cookie" not in hdrs
    assert "Host" not in hdrs
    assert "Content-Length" not in hdrs
    assert hdrs.get("Content-Type") == "application/json"
    assert hdrs.get("X-Custom") == "keep-me"


@pytest.mark.unit
def test_login_detection_default(tmp_path):
    har = make_har(entries=[
        _entry(url="http://h:8000/user/login"),
        _entry(url="http://h:8000/walker/search"),
    ])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://t:9000")
    assert entries[0].is_login is True
    assert entries[1].is_login is False


@pytest.mark.unit
def test_login_detection_custom_path(tmp_path):
    har = make_har(entries=[
        _entry(url="http://h:8000/api/auth"),
        _entry(url="http://h:8000/user/login"),
    ])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://t:9000", login_path="/api/auth")
    assert entries[0].is_login is True
    assert entries[1].is_login is False


@pytest.mark.unit
def test_think_time_extraction(tmp_path):
    har = make_har(entries=[
        _entry(wait=123),
    ])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://t:9000")
    assert entries[0].think_time_ms == 123.0


@pytest.mark.unit
def test_security_warning_emitted(tmp_path, capsys):
    path = str(tmp_path / "min.har")
    import shutil, os
    fixtures = os.path.join(os.path.dirname(__file__), "../fixtures/minimal.har")
    shutil.copy(fixtures, path)
    parse_har(path, target_url="http://t:9000")
    captured = capsys.readouterr()
    assert "Authorization" in captured.err or "Cookie" in captured.err or "sensitive" in captured.err


@pytest.mark.unit
def test_security_warning_suppressed(tmp_path, capsys):
    har = make_har(entries=[
        _entry(url="http://h:8000/walker/search", headers=[
            {"name": "Content-Type", "value": "application/json"}
        ])
    ])
    path = _write_har(tmp_path, har)
    parse_har(path, target_url="http://t:9000")
    captured = capsys.readouterr()
    assert "Warning" not in captured.err


@pytest.mark.unit
def test_har_1_1_compat(tmp_path):
    """HAR 1.1 entries have no 'ssl' timing field — must parse without error."""
    entry = {
        "request": {
            "method": "GET",
            "url": "http://h:8000/ping",
            "headers": [],
            "queryString": [],
        },
        "response": {"status": 200, "content": {"mimeType": "application/json"}},
        "timings": {"send": 1, "wait": 10, "receive": 2},  # no ssl field
    }
    har = {"log": {"version": "1.1", "entries": [entry]}}
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://t:9000")
    assert len(entries) == 1
    assert entries[0].think_time_ms == 10.0


@pytest.mark.unit
def test_entry_order_preserved(tmp_path):
    har = make_har(entries=[
        _entry(url="http://h:8000/a"),
        _entry(url="http://h:8000/b"),
        _entry(url="http://h:8000/c"),
    ])
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://t:9000")
    paths = [e.original_url for e in entries]
    assert paths == [
        "http://h:8000/a",
        "http://h:8000/b",
        "http://h:8000/c",
    ]


@pytest.mark.unit
def test_empty_har(tmp_path):
    har = {"log": {"version": "1.2", "entries": []}}
    path = _write_har(tmp_path, har)
    entries = parse_har(path, target_url="http://t:9000")
    assert entries == []


@pytest.mark.unit
def test_malformed_har_missing_log(tmp_path):
    har = {"not_log": {}}
    path = _write_har(tmp_path, har)
    with pytest.raises(ValueError, match="log"):
        parse_har(path, target_url="http://t:9000")
