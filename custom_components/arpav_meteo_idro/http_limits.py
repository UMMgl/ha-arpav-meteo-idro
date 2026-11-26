# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Bounded readers for the HTTP responses of the fixed upstream endpoints."""

from __future__ import annotations

import json
from typing import Any

import aiohttp

# a station XML file is ~20-40 kB
MAX_XML_RESPONSE_BYTES = 5 * 1024 * 1024
# the largest JSON listings are a few hundred kB
MAX_JSON_RESPONSE_BYTES = 10 * 1024 * 1024

_CHUNK_BYTES = 64 * 1024


class ResponseTooLargeError(aiohttp.ClientPayloadError, ValueError):
    """The body of a response exceeds the allowed size."""


async def read_limited(
    response: aiohttp.ClientResponse, max_bytes: int = MAX_XML_RESPONSE_BYTES
) -> bytes:
    """Read a response body, aborting as soon as it exceeds ``max_bytes``.

    The limit applies to the decoded body, so it also bounds compressed responses.
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
    response: aiohttp.ClientResponse, max_bytes: int = MAX_JSON_RESPONSE_BYTES
) -> Any:
    """Read and decode a JSON body, refusing bodies bigger than ``max_bytes``."""
    return json.loads(await read_limited(response, max_bytes))
