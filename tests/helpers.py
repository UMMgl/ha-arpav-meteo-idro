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


class FakeContent:
    """Stand-in for ``aiohttp.StreamReader``: the body, delivered in chunks."""

    def __init__(self, body: bytes, chunk_size: int | None = None):
        """Hold the body and the size of the chunks it is delivered in."""
        self._body = body
        self._chunk_size = chunk_size

    async def iter_chunked(self, n):
        """Yield the body in chunks, none bigger than ``n`` bytes."""
        size = min(n, self._chunk_size or n)
        for start in range(0, len(self._body), size):
            yield self._body[start:start + size]


class FakeResponse:
    """Minimal stand-in for an aiohttp response.

    ``payload`` is served as the JSON body, unless ``body`` gives the raw bytes.
    ``headers`` are merged over a JSON ``Content-Type``; there is no
    ``Content-Length`` unless ``declared_length`` sets one (it may lie).
    """

    def __init__(self, payload=None, status=200, *, body=None, headers=None,
                 declared_length=None, chunk_size=None, charset=None):
        """Hold the payload and status to serve."""
        self.status = status
        self.charset = charset
        self.request_info = None
        self.history = ()
        raw = body if body is not None else json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Type": "application/json"}
        if declared_length is not None:
            self.headers["Content-Length"] = str(declared_length)
        self.headers.update(headers or {})
        self.content = FakeContent(raw, chunk_size)

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


class FakeSession:
    """Serve the payload of the first route whose key is contained in the URL.

    A route value may be a payload, a ``(payload, status)`` tuple or an exception
    instance, which is raised on ``get``, or a ready ``FakeResponse``. Requested URLs
    are kept in ``requests``.
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
                if isinstance(value, FakeResponse):
                    return value
                if isinstance(value, tuple):
                    return FakeResponse(*value)
                return FakeResponse(value)
        raise AssertionError(f"unexpected request: {url}")
