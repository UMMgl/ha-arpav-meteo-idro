# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Bounded readers for the HTTP responses of the fixed upstream endpoints.

Every body is read in chunks and the download is aborted as soon as it goes over
the limit, instead of being buffered whole and checked afterwards.
"""

from __future__ import annotations

import json
import re
from typing import Any

import aiohttp

# the largest JSON listings (the ARPAV station and municipality lists) are a few
# hundred kB: 10 MiB leaves a wide margin and still bounds memory
MAX_JSON_RESPONSE_BYTES = 10 * 1024 * 1024

_CHUNK_BYTES = 64 * 1024
# the same test aiohttp applies in ``ClientResponse.json``
_JSON_CONTENT_TYPE = re.compile(r"^application/(?:[\w.+-]+?\+)?json")


class ResponseTooLargeError(aiohttp.ClientPayloadError, ValueError):
    """The body of a response exceeds the allowed size.

    It is an ``aiohttp.ClientError``, so every caller that already treats a failed
    request as an unusable answer treats an oversized one the same way.
    """


async def read_limited(response: aiohttp.ClientResponse, max_bytes: int) -> bytes:
    """Read a response body, aborting as soon as it exceeds ``max_bytes``.

    The limit applies to the decoded body, so it also bounds compressed responses.
    A declared ``Content-Length`` over the limit is refused without reading; a
    missing or understated one is caught by counting the bytes received.
    """
    declared = response.headers.get("Content-Length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise ResponseTooLargeError("response too large")

    body = bytearray()
    async for chunk in response.content.iter_chunked(_CHUNK_BYTES):
        body.extend(chunk)
        if len(body) > max_bytes:
            raise ResponseTooLargeError("response too large")
    return bytes(body)


async def read_json_limited(
    response: aiohttp.ClientResponse, max_bytes: int | None = None
) -> Any:
    """Read and decode a JSON body, refusing bodies bigger than ``max_bytes``.

    The default limit is ``MAX_JSON_RESPONSE_BYTES``.

    It behaves like ``ClientResponse.json``: a response that is not declared as
    JSON raises ``aiohttp.ContentTypeError`` and an empty body gives ``None``.
    """
    content_type = response.headers.get("Content-Type", "").lower()
    if not _JSON_CONTENT_TYPE.match(content_type):
        raise aiohttp.ContentTypeError(
            response.request_info,
            response.history,
            status=response.status,
            message=f"Attempt to decode JSON with unexpected mimetype: {content_type}",
            headers=response.headers,
        )

    body = (
        await read_limited(response, MAX_JSON_RESPONSE_BYTES if max_bytes is None else max_bytes)
    ).strip()
    if not body:
        return None
    return json.loads(body.decode(response.charset or "utf-8"))
