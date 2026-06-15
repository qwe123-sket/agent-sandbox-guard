from __future__ import annotations

from urllib.parse import urlparse

import httpx

from agent_guard.sandbox import SandboxError


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SandboxError(f"不支持的协议: {parsed.scheme}")
    if not parsed.netloc:
        raise SandboxError("URL 缺少 host")


def http_get(url: str, timeout: float = 10.0) -> dict:
    _validate_url(url)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body_preview": response.text[:1000],
    }


def http_post(url: str, json_body: dict | None = None, timeout: float = 10.0) -> dict:
    _validate_url(url)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.post(url, json=json_body or {})
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body_preview": response.text[:1000],
    }
