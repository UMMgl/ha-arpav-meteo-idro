# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Shared helpers: a fake aiohttp session serving recorded fixtures."""

import json
import pathlib

import aiohttp

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_json(name: str):
    """Return a JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    """Minimal stand-in for an aiohttp response."""

    def __init__(self, payload, status=200):
        """Hold the payload and status to serve."""
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        """Enter the context."""
        return self

    async def __aexit__(self, *exc):
        """Leave the context."""
        return False

    def raise_for_status(self):
        """Raise like aiohttp on error statuses."""
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status)

    async def json(self):
        """Return the payload."""
        return self._payload


class FakeSession:
    """Serve the payload of the first route whose key is contained in the URL.

    A route value may be a payload, a ``(payload, status)`` tuple or an exception
    instance, which is raised on ``get``. Requested URLs are kept in ``requests``.
    """

    def __init__(self, routes):
        """Hold the routes to serve."""
        self.routes = routes
        self.requests = []

    async def __aenter__(self):
        """Enter the context."""
        return self

    async def __aexit__(self, *exc):
        """Leave the context."""
        return False

    def get(self, url, **_kwargs):
        """Serve a request."""
        self.requests.append(url)
        for key, value in self.routes.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                if isinstance(value, tuple):
                    return FakeResponse(*value)
                return FakeResponse(value)
        raise AssertionError(f"unexpected request: {url}")
