# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Redirect handling of ``async_fetch_document``: every hop stays on the ARPAV origin."""

import pathlib

import aiohttp
import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.helpers.aiohttp_client import async_get_clientsession  # noqa: E402

from custom_components.arpav_meteo_idro import http_limits, hydro, hydro_coordinator  # noqa: E402

HOST = "https://meteo.arpa.veneto.it"
DOC = f"{hydro.XML_BASE}/0287.xml"
DOC_BYTES = (pathlib.Path(__file__).parent / "fixtures" / "0287.xml").read_bytes()


def _redirect(mock, url, location, status=302):
    mock.get(url, status=status, headers={"Location": location})


async def test_redirect_within_arpav_host_is_followed(enable_custom_integrations, hass, aioclient_mock):
    """Absolute, root-relative and path-relative redirects on the ARPAV origin work."""
    session = async_get_clientsession(hass)
    _redirect(aioclient_mock, f"{HOST}/a", f"{HOST}/b", 301)
    _redirect(aioclient_mock, f"{HOST}/b", "/meteo/c", 307)
    _redirect(aioclient_mock, f"{HOST}/meteo/c", "d.xml", 308)
    aioclient_mock.get(f"{HOST}/meteo/d.xml", content=DOC_BYTES)
    assert await hydro_coordinator.async_fetch_document(session, f"{HOST}/a") == DOC_BYTES
    assert aioclient_mock.call_count == 4


async def test_explicit_default_port_is_the_same_origin(enable_custom_integrations, hass, aioclient_mock):
    """An explicit :443 is the same origin as the implicit one."""
    session = async_get_clientsession(hass)
    _redirect(aioclient_mock, DOC, "https://meteo.arpa.veneto.it:443/meteo/x.xml")
    aioclient_mock.get(f"{HOST}/meteo/x.xml", content=DOC_BYTES)
    assert await hydro_coordinator.async_fetch_document(session, DOC) == DOC_BYTES


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example/x.xml",  # another host
        "https://meteo.arpa.veneto.it.evil.example/x.xml",  # look-alike host
        "http://meteo.arpa.veneto.it/x.xml",  # another scheme
        "ftp://meteo.arpa.veneto.it/x.xml",
        "https://user:pw@meteo.arpa.veneto.it/x.xml",  # userinfo
        "https://user@meteo.arpa.veneto.it/x.xml",
        "https://meteo.arpa.veneto.it:8443/x.xml",  # another port
        "https://meteo.arpa.veneto.it:abc/x.xml",  # malformed port
        "//evil.example/x.xml",  # scheme-relative, other host
        "https://169.254.169.254/latest/meta-data",
    ],
)
async def test_redirect_elsewhere_is_rejected(enable_custom_integrations, hass, aioclient_mock, location):
    """A redirect to any other destination is a failed request and is never requested."""
    session = async_get_clientsession(hass)
    _redirect(aioclient_mock, DOC, location)
    with pytest.raises(aiohttp.ClientError):
        await hydro_coordinator.async_fetch_document(session, DOC)
    assert aioclient_mock.call_count == 1


async def test_redirect_without_location_is_rejected(enable_custom_integrations, hass, aioclient_mock):
    """A redirect that names no destination is a failed request."""
    session = async_get_clientsession(hass)
    aioclient_mock.get(DOC, status=302)
    with pytest.raises(aiohttp.ClientError):
        await hydro_coordinator.async_fetch_document(session, DOC)


async def test_redirect_loop_is_rejected(enable_custom_integrations, hass, aioclient_mock):
    """A redirect loop stops after the hop limit."""
    session = async_get_clientsession(hass)
    _redirect(aioclient_mock, f"{HOST}/a", f"{HOST}/b")
    _redirect(aioclient_mock, f"{HOST}/b", f"{HOST}/a")
    with pytest.raises(aiohttp.ClientError, match="too many redirects"):
        await hydro_coordinator.async_fetch_document(session, f"{HOST}/a")
    assert aioclient_mock.call_count == hydro_coordinator.MAX_REDIRECTS + 1


async def test_redirect_hop_limit(enable_custom_integrations, hass, aioclient_mock):
    """Five hops are followed, a sixth is refused."""
    session = async_get_clientsession(hass)
    for hop in range(1, 6):
        _redirect(aioclient_mock, f"{HOST}/h{hop - 1}", f"{HOST}/h{hop}")
    aioclient_mock.get(f"{HOST}/h5", content=DOC_BYTES)
    assert await hydro_coordinator.async_fetch_document(session, f"{HOST}/h0") == DOC_BYTES

    aioclient_mock.clear_requests()
    for hop in range(1, 7):
        _redirect(aioclient_mock, f"{HOST}/h{hop - 1}", f"{HOST}/h{hop}")
    aioclient_mock.get(f"{HOST}/h6", content=DOC_BYTES)
    with pytest.raises(aiohttp.ClientError, match="too many redirects"):
        await hydro_coordinator.async_fetch_document(session, f"{HOST}/h0")


async def test_start_url_outside_arpav_is_rejected(enable_custom_integrations, hass, aioclient_mock):
    """The first URL is validated too, before any request is made."""
    session = async_get_clientsession(hass)
    with pytest.raises(aiohttp.ClientError):
        await hydro_coordinator.async_fetch_document(session, "https://evil.example/x.xml")
    assert aioclient_mock.call_count == 0


async def test_size_limit_applies_after_a_redirect(enable_custom_integrations, hass, aioclient_mock, monkeypatch):
    """The size limit applies to the response reached after a redirect."""
    session = async_get_clientsession(hass)
    _redirect(aioclient_mock, DOC, f"{HOST}/meteo/big.xml")
    aioclient_mock.get(f"{HOST}/meteo/big.xml", content=b"x" * 2000)
    monkeypatch.setattr(hydro, "MAX_XML_BYTES", 1000)
    with pytest.raises(http_limits.ResponseTooLargeError):
        await hydro_coordinator.async_fetch_document(session, DOC)
