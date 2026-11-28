# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Config and options flow steps for the ARPAV hydrometric stations."""

from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import slugify

from . import hydro
from .const import (
    CONF_ENTRY_TYPE,
    CONF_HYDRO_AXIS_CEILING,
    CONF_HYDRO_ARCHIVE,
    CONF_HYDRO_RIVER,
    CONF_HYDRO_STALE_MINUTES,
    CONF_HYDRO_STALE_MINUTES_DEFAULT,
    CONF_HYDRO_STATIONS,
    CONF_HYDRO_TREND_THRESHOLD,
    CONF_HYDRO_TREND_THRESHOLD_DEFAULT,
    ENTRY_TYPE_HYDRO,
)
from .hydro_coordinator import async_fetch_registry, station_meta
from .hydro_topology import ordered_selection, station_key

_LOGGER = logging.getLogger(__name__)

STEP_STATIONS = "stations"


def parse_ceilings(text: str | None, station_ids: list[str]) -> dict[str, float] | None:
    """Return the axis ceilings typed by the user, or None when they are invalid.

    The format is ``station_id=metres`` separated by commas; every station must
    be one of ``station_ids`` (the stations of the entry, matched like the order
    field, so ``0334`` and ``334`` are the same station) and every value in
    (0, 100] metres. The result is keyed by the ID saved in the entry.
    """
    ceilings = hydro.parse_axis_ceilings(text)
    if ceilings is None:
        return None
    by_key = {station_key(station_id): station_id for station_id in station_ids}
    if any(station_key(station_id) not in by_key for station_id in ceilings):
        return None
    return {by_key[station_key(station_id)]: value for station_id, value in ceilings.items()}


def river_options(
    registry: list[hydro.HydroStation], home_latitude: float | None, home_longitude: float | None
) -> list[selector.SelectOptionDict]:
    """Return the river choices, nearest to home first, each labelled with its distance.

    The value is always the plain river name (it builds the unique ID of the entry).
    Without a usable home position the list is alphabetical and has no distances.
    The position and the distances are only used here: never logged, never stored.
    """
    return [
        selector.SelectOptionDict(
            value=river, label=river if km is None else f"{river} – {km:.0f} km")
        for river, km in hydro.rivers_by_distance(registry, home_latitude, home_longitude)
    ]


def _station_options(
    stations: list[hydro.HydroStation],
    home: tuple[float | None, float | None] | None = None,
) -> list[selector.SelectOptionDict]:
    options = []
    for s in stations:
        label = f"{s.place or s.name} ({s.station_id})"
        km = hydro.station_distance(s, *home) if home else None
        if km is not None:
            label = f"{label} – {km:.0f} km"
        options.append(selector.SelectOptionDict(value=s.station_id, label=label))
    return options


def _stations_schema(stations, selected, extra=None, home=None) -> vol.Schema:
    schema = {
        vol.Required(STEP_STATIONS, default=selected): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_station_options(stations, home), multiple=True,
                                          mode=selector.SelectSelectorMode.LIST)
        ),
    }
    schema.update(extra or {})
    return vol.Schema(schema)


def _order_hint(stations) -> str:
    return ", ".join(f"{s.station_id} = {s.place or s.name}" for s in stations)


class HydroConfigFlowMixin:
    """Steps of the config flow creating an entry of hydrometric stations."""

    _hydro_registry: list[hydro.HydroStation]
    _hydro_river: str

    async def async_step_hydro(self, user_input=None):
        """Choose the river (water body)."""
        errors = {}
        try:
            self._hydro_registry = await async_fetch_registry(self.hass)
        except (aiohttp.ClientError, TimeoutError, hydro.HydroParseError) as err:
            _LOGGER.warning("Unable to read the ARPAV hydrometric registry: %s", err)
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            self._hydro_river = user_input[CONF_HYDRO_RIVER]
            await self.async_set_unique_id(f"{ENTRY_TYPE_HYDRO}_{slugify(self._hydro_river)}")
            self._abort_if_unique_id_configured()
            return await self.async_step_hydro_stations()

        return self.async_show_form(
            step_id="hydro",
            data_schema=vol.Schema({
                vol.Required(CONF_HYDRO_RIVER): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=river_options(
                                                      self._hydro_registry,
                                                      self.hass.config.latitude,
                                                      self.hass.config.longitude),
                                                  mode=selector.SelectSelectorMode.DROPDOWN)
                ),
            }),
            errors=errors,
        )

    async def async_step_hydro_stations(self, user_input=None):
        """Choose the stations of the river."""
        stations = [s for s in self._hydro_registry if s.river == self._hydro_river]
        errors = {}
        if user_input is not None:
            if not user_input[STEP_STATIONS]:
                errors["base"] = "no_stations"
            else:
                ordered = ordered_selection(user_input[STEP_STATIONS], self._hydro_river)
                by_id = {s.station_id: s for s in stations}
                return self.async_create_entry(
                    title=f"{self._hydro_river} (ARPAV)",
                    data={CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO, CONF_HYDRO_RIVER: self._hydro_river},
                    options={
                        CONF_HYDRO_STATIONS: [station_meta(by_id[i]) for i in ordered],
                        CONF_HYDRO_TREND_THRESHOLD: CONF_HYDRO_TREND_THRESHOLD_DEFAULT,
                        CONF_HYDRO_STALE_MINUTES: CONF_HYDRO_STALE_MINUTES_DEFAULT,
                        CONF_HYDRO_ARCHIVE: True,
                    },
                )

        return self.async_show_form(
            step_id="hydro_stations",
            data_schema=_stations_schema(
                stations, [], home=(self.hass.config.latitude, self.hass.config.longitude)),
            errors=errors,
            description_placeholders={"river": self._hydro_river, "stations": _order_hint(stations)},
        )


class HydroOptionsFlowHandler(config_entries.OptionsFlow):
    """Options of an entry of hydrometric stations."""

    async def async_step_init(self, user_input=None):
        """Open the hydrometric options (a step of their own for the translations)."""
        return await self.async_step_hydro_options(user_input)

    async def async_step_hydro_options(self, user_input=None):
        """Manage stations, trend threshold, staleness, axis ceiling and archive."""
        river = self.config_entry.data.get(CONF_HYDRO_RIVER)
        options = self.config_entry.options
        current = options.get(CONF_HYDRO_STATIONS, [])
        try:
            registry = await async_fetch_registry(self.hass)
            stations = [s for s in registry if s.river == river]
        except (aiohttp.ClientError, TimeoutError, hydro.HydroParseError) as err:
            _LOGGER.warning("Unable to read the ARPAV hydrometric registry: %s", err)
            return self.async_abort(reason="cannot_connect")

        errors = {}
        if user_input is not None:
            ordered = ordered_selection(user_input[STEP_STATIONS], river)
            if not user_input[STEP_STATIONS]:
                errors["base"] = "no_stations"
            elif (ceilings := parse_ceilings(user_input.get(CONF_HYDRO_AXIS_CEILING), ordered)) is None:
                errors[CONF_HYDRO_AXIS_CEILING] = "invalid_axis_ceiling"
            else:
                by_id = {s.station_id: s for s in stations}
                known = {m["id"]: m for m in current}
                return self.async_create_entry(data={
                    CONF_HYDRO_STATIONS: [station_meta(by_id[i]) if i in by_id else known[i] for i in ordered],
                    CONF_HYDRO_AXIS_CEILING: ceilings,
                    CONF_HYDRO_TREND_THRESHOLD: user_input[CONF_HYDRO_TREND_THRESHOLD],
                    CONF_HYDRO_STALE_MINUTES: user_input[CONF_HYDRO_STALE_MINUTES],
                    CONF_HYDRO_ARCHIVE: user_input[CONF_HYDRO_ARCHIVE],
                })

        extra = {
            vol.Optional(CONF_HYDRO_TREND_THRESHOLD,
                         default=options.get(CONF_HYDRO_TREND_THRESHOLD, CONF_HYDRO_TREND_THRESHOLD_DEFAULT)):
                selector.NumberSelector(selector.NumberSelectorConfig(
                    min=1, max=100, step=1, unit_of_measurement="cm", mode=selector.NumberSelectorMode.BOX)),
            vol.Optional(CONF_HYDRO_STALE_MINUTES,
                         default=options.get(CONF_HYDRO_STALE_MINUTES, CONF_HYDRO_STALE_MINUTES_DEFAULT)):
                selector.NumberSelector(selector.NumberSelectorConfig(
                    min=0, max=1440, step=5, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)),
            vol.Optional(CONF_HYDRO_ARCHIVE, default=options.get(CONF_HYDRO_ARCHIVE, True)): bool,
            # a suggested value, not a default: an emptied field is omitted by the
            # frontend and a default would bring the old ceilings back
            vol.Optional(CONF_HYDRO_AXIS_CEILING,
                         description={"suggested_value": hydro.format_axis_ceilings(
                             options.get(CONF_HYDRO_AXIS_CEILING) or {})}):
                selector.TextSelector(),
        }
        return self.async_show_form(
            step_id="hydro_options",
            data_schema=_stations_schema(stations, [m["id"] for m in current], extra),
            errors=errors,
            description_placeholders={"river": river, "stations": _order_hint(stations)},
        )
