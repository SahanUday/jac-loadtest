"""Parse HAR 1.2 files, filter non-API entries, and rewrite URLs.

core/ has zero knowledge of jac-scale internals.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


_SKIP_MIME_PREFIXES = (
    "image/",
    "font/",
    "text/css",
    "application/javascript",
    "text/javascript",
    "application/wasm",
)

_STRIP_HEADERS = {"authorization", "cookie", "host", "content-length"}


@dataclass
class HarEntry:
    method: str
    url: str
    headers: dict[str, str]
    body: str | None
    body_mime: str | None
    think_time_ms: float
    is_login: bool
    original_url: str


def _origin(url: str) -> str:
    """Return scheme://host:port (no path) from a URL."""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, "", "", "", ""))


def _rewrite_url(original: str, recorded_origin: str, target_url: str) -> str:
    """Replace recorded origin with target_url, preserving path and query."""
    p = urlparse(original)
    t = urlparse(target_url)
    rewritten = urlunparse((t.scheme, t.netloc, p.path, p.params, p.query, ""))
    return rewritten


def _is_static(mime: str) -> bool:
    if not mime:
        return False
    mime_lower = mime.lower().split(";")[0].strip()
    return any(mime_lower.startswith(prefix) for prefix in _SKIP_MIME_PREFIXES)


def parse_har(
    har_path: str,
    target_url: str,
    include_static: bool = False,
    login_path: str = "/user/login",
) -> list[HarEntry]:
    """Parse a HAR 1.2 file and return filtered, URL-rewritten HarEntry objects."""
    with open(har_path, encoding="utf-8") as f:
        data = json.load(f)

    if "log" not in data:
        raise ValueError("Malformed HAR file: missing 'log' key")

    _check_version(data["log"].get("version", "unknown"))

    raw_entries = data["log"].get("entries", [])

    if not raw_entries:
        return []

    recorded_origin = _origin(raw_entries[0]["request"]["url"])

    # Security scan — warn once if any auth headers found
    _security_scan(raw_entries)

    result: list[HarEntry] = []
    for entry in raw_entries:
        req = entry["request"]
        resp = entry.get("response", {})
        content = resp.get("content", {})
        mime = content.get("mimeType", "")

        if not include_static and _is_static(mime):
            continue

        original_url = req["url"]
        rewritten_url = _rewrite_url(original_url, recorded_origin, target_url)

        headers = _sanitize_headers(req.get("headers", []))

        post_data = req.get("postData", {}) or {}
        body = post_data.get("text") or None
        body_mime = post_data.get("mimeType") or None

        timings = entry.get("timings", {})
        think_time_ms = float(timings.get("wait", 0.0))

        is_login = urlparse(original_url).path == login_path

        result.append(
            HarEntry(
                method=req["method"].upper(),
                url=rewritten_url,
                headers=headers,
                body=body,
                body_mime=body_mime,
                think_time_ms=think_time_ms,
                is_login=is_login,
                original_url=original_url,
            )
        )

    return result


_SUPPORTED_HAR_VERSIONS = {"1.1", "1.2"}


def _check_version(version: str) -> None:
    """Warn if the HAR version is outside the tested range."""
    if version not in _SUPPORTED_HAR_VERSIONS:
        print(
            f"Warning: HAR version '{version}' is not tested with this tool "
            f"(tested: {', '.join(sorted(_SUPPORTED_HAR_VERSIONS))}).\n"
            "Parsing will continue but results may be incomplete or incorrect.\n"
            "If the output looks wrong, check for a jac-loadtest update.",
            file=sys.stderr,
        )


def _security_scan(entries: list[dict]) -> None:
    """Emit a stderr warning if any HAR entry contains auth/cookie headers."""
    for entry in entries:
        for hdr in entry.get("request", {}).get("headers", []):
            name = hdr.get("name", "").lower()
            value = hdr.get("value", "")
            if name in ("authorization", "cookie") and value:
                print(
                    "Warning: HAR file contains Authorization/Cookie headers from the "
                    "recording session.\nThese headers are stripped before replay, but "
                    "the file itself contains sensitive data.\n"
                    "Do not commit this HAR file to version control.",
                    file=sys.stderr,
                )
                return


def _sanitize_headers(raw_headers: list[dict]) -> dict[str, str]:
    """Strip session-specific headers; return clean dict."""
    return {
        h["name"]: h["value"]
        for h in raw_headers
        if h.get("name", "").lower() not in _STRIP_HEADERS
    }
