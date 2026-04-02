#!/usr/bin/env python3
"""Shared HTTPS helpers for ad-engine providers."""

from __future__ import annotations

import ssl
import urllib.request
from typing import Any

try:
    import certifi
except Exception:  # pragma: no cover - optional dependency
    certifi = None


def _ssl_context() -> ssl.SSLContext | None:
    if certifi is None:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def urlopen(
    req: urllib.request.Request | str,
    *,
    timeout: int = 90,
) -> Any:
    context = _ssl_context()
    if context is None:
        return urllib.request.urlopen(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=context)
