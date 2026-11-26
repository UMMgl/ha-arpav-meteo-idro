# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Tests of the bounded response readers (no Home Assistant, no network)."""

import json

import aiohttp
import pytest

from custom_components.arpav_meteo_idro import http_limits
from custom_components.arpav_meteo_idro.http_limits import (
    MAX_JSON_RESPONSE_BYTES,
    ResponseTooLargeError,
    read_json_limited,
    read_limited,
)

from .helpers import FIXTURES, FakeResponse


class CountingResponse(FakeResponse):
    """A response that records how many chunks were pulled from the body."""

    def __init__(self, *args, **kwargs):
        """Wrap the content so that every delivered chunk is counted."""
        super().__init__(*args, **kwargs)
        self.chunks = 0
        inner = self.content

        class Content:
            async def iter_chunked(_, n):  # noqa: N805
                async for chunk in inner.iter_chunked(n):
                    self.chunks += 1
                    yield chunk

        self.content = Content()


def _response(body: bytes, **kwargs) -> FakeResponse:
    return FakeResponse(body=body, **kwargs)


async def test_body_within_the_limit_is_returned_whole():
    """A body under the limit comes back unchanged."""
    assert await read_limited(_response(b"x" * 100), 1000) == b"x" * 100


async def test_body_exactly_at_the_limit_is_accepted():
    """The limit is inclusive; one byte more is refused."""
    assert await read_limited(_response(b"x" * 100), 100) == b"x" * 100
    with pytest.raises(ResponseTooLargeError):
        await read_limited(_response(b"x" * 101), 100)


async def test_empty_body_is_returned_as_is():
    """No chunks at all is not an error for the reader."""
    assert await read_limited(_response(b""), 10) == b""


async def test_oversized_body_without_content_length_is_aborted_while_reading():
    """Without a declared length the download stops as soon as the limit is passed."""
    response = CountingResponse(body=b"x" * (64 * 1024 * 20), chunk_size=1024)
    with pytest.raises(ResponseTooLargeError):
        await read_limited(response, 4096)
    assert response.chunks == 5  # 5 x 1 kB is the first total over 4 kB: not the 1280 chunks


async def test_oversized_content_length_is_refused_before_reading():
    """A declared length over the limit is refused without reading a byte."""
    response = CountingResponse(body=b"x" * 10, declared_length=10_000)
    with pytest.raises(ResponseTooLargeError):
        await read_limited(response, 100)
    assert response.chunks == 0


async def test_lying_content_length_is_caught_by_counting_the_bytes():
    """A short declared length does not let a bigger body through."""
    response = CountingResponse(body=b"x" * 5000, declared_length=10, chunk_size=1000)
    with pytest.raises(ResponseTooLargeError):
        await read_limited(response, 2500)
    assert response.chunks == 3


async def test_content_length_that_is_not_a_number_is_ignored():
    """A malformed header must not hide the real size."""
    assert await read_limited(_response(b"abc", headers={"Content-Length": "many"}), 10) == b"abc"
    with pytest.raises(ResponseTooLargeError):
        await read_limited(_response(b"x" * 20, headers={"Content-Length": "many"}), 10)


async def test_chunked_delivery_is_reassembled_in_order():
    """Chunks smaller than the read size are joined without loss."""
    body = bytes(range(256)) * 40
    assert await read_limited(_response(body, chunk_size=7), len(body)) == body


async def test_too_large_error_is_a_client_error():
    """The callers that catch aiohttp.ClientError treat it as an unusable answer."""
    assert issubclass(ResponseTooLargeError, aiohttp.ClientError)
    assert issubclass(ResponseTooLargeError, ValueError)


async def test_json_within_the_limit_is_decoded():
    """The recorded payloads decode like response.json()."""
    payload = {"data": [{"a": 1}, {"b": "è"}]}
    assert await read_json_limited(FakeResponse(payload)) == payload


async def test_json_over_the_limit_is_refused(monkeypatch):
    """The default limit is the module constant, resolved on every call."""
    monkeypatch.setattr(http_limits, "MAX_JSON_RESPONSE_BYTES", 10)
    with pytest.raises(ResponseTooLargeError):
        await read_json_limited(FakeResponse({"data": list(range(50))}))
    assert await read_json_limited(FakeResponse([1])) == [1]


async def test_json_explicit_limit_overrides_the_default():
    """A caller may pass its own limit."""
    with pytest.raises(ResponseTooLargeError):
        await read_json_limited(FakeResponse({"data": list(range(50))}), 10)


async def test_invalid_json_raises_value_error():
    """A body that is not JSON fails like response.json() did."""
    with pytest.raises(json.JSONDecodeError):
        await read_json_limited(_response(b"{not json"))


async def test_empty_json_body_is_none():
    """An empty (or blank) body gives None, as response.json() does."""
    assert await read_json_limited(_response(b"")) is None
    assert await read_json_limited(_response(b" \n")) is None


@pytest.mark.parametrize("content_type", ["text/html", "", "application/xml"])
async def test_json_with_another_content_type_is_refused(content_type):
    """Like response.json(), a body not declared as JSON is not decoded."""
    response = _response(b"[]", headers={"Content-Type": content_type})
    with pytest.raises(aiohttp.ContentTypeError):
        await read_json_limited(response)


@pytest.mark.parametrize("content_type", [
    "application/json", "application/json; charset=utf-8", "Application/JSON",
    "application/vnd.api+json",
])
async def test_json_content_types_accepted(content_type):
    """Parameters, case and the +json suffix are accepted."""
    assert await read_json_limited(_response(b"[1]", headers={"Content-Type": content_type})) == [1]


async def test_json_honours_the_declared_charset():
    """The body is decoded with the charset of the response, UTF-8 by default."""
    text = '{"nome": "Città"}'
    assert await read_json_limited(_response(text.encode("latin-1"), charset="latin-1")) == {"nome": "Città"}
    assert await read_json_limited(_response(text.encode("utf-8"))) == {"nome": "Città"}


def test_the_recorded_payloads_are_far_below_the_limits():
    """The real ARPAV and METAR payloads in the fixtures use a tiny share of the limit."""
    sizes = [path.stat().st_size for path in FIXTURES.glob("*.json")]
    assert sizes
    assert max(sizes) < MAX_JSON_RESPONSE_BYTES // 1000
