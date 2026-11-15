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
    CONF_HYDRO_ORDER,
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


def _station_options(stations: list[hydro.HydroStation]) -> list[selector.SelectOptionDict]:
    return [selector.SelectOptionDict(value=s.station_id, label=f"{s.place or s.name} ({s.station_id})")
            for s in stations]


def _stations_schema(stations, selected, order_text, extra=None) -> vol.Schema:
    schema = {
        vol.Required(STEP_STATIONS, default=selected): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_station_options(stations), multiple=True,
                                          mode=selector.SelectSelectorMode.LIST)
        ),
        vol.Optional(CONF_HYDRO_ORDER, description={"suggested_value": order_text}): selector.TextSelector(),
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
                    selector.SelectSelectorConfig(options=hydro.rivers(self._hydro_registry),
                                                  mode=selector.SelectSelectorMode.DROPDOWN)
                ),
            }),
            errors=errors,
        )

    async def async_step_hydro_stations(self, user_input=None):
        """Choose the stations of the river and their order, upstream first."""
        stations = [s for s in self._hydro_registry if s.river == self._hydro_river]
        errors = {}
        if user_input is not None:
            order_text = user_input.get(CONF_HYDRO_ORDER, "").strip()
            ordered = ordered_selection(user_input[STEP_STATIONS], order_text, self._hydro_river)
            if not user_input[STEP_STATIONS]:
                errors["base"] = "no_stations"
            elif ordered is None:
                errors[CONF_HYDRO_ORDER] = "invalid_order"
            else:
                by_id = {s.station_id: s for s in stations}
                return self.async_create_entry(
                    title=f"{self._hydro_river} (ARPAV)",
                    data={CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO, CONF_HYDRO_RIVER: self._hydro_river},
                    options={
                        CONF_HYDRO_STATIONS: [station_meta(by_id[i]) for i in ordered],
                        CONF_HYDRO_ORDER: order_text,
                        CONF_HYDRO_TREND_THRESHOLD: CONF_HYDRO_TREND_THRESHOLD_DEFAULT,
                        CONF_HYDRO_STALE_MINUTES: CONF_HYDRO_STALE_MINUTES_DEFAULT,
                        CONF_HYDRO_ARCHIVE: True,
                    },
                )

        return self.async_show_form(
            step_id="hydro_stations",
            data_schema=_stations_schema(stations, [], ""),
            errors=errors,
            description_placeholders={"river": self._hydro_river, "stations": _order_hint(stations)},
        )


class HydroOptionsFlowHandler(config_entries.OptionsFlow):
    """Options of an entry of hydrometric stations."""

    async def async_step_init(self, user_input=None):
        """Open the hydrometric options (a step of their own for the translations)."""
        return await self.async_step_hydro_options(user_input)

    async def async_step_hydro_options(self, user_input=None):
        """Manage stations, order, trend threshold, staleness and archive."""
        river = self.config_entry.data.get(CONF_HYDRO_RIVER)
        options = self.config_entry.options
        current = options.get(CONF_HYDRO_STATIONS, [])
        # Existing entries only saved the resulting order. Pre-fill it as an override.
        saved_order = options.get(CONF_HYDRO_ORDER, ", ".join(m["id"] for m in current))
        try:
            registry = await async_fetch_registry(self.hass)
            stations = [s for s in registry if s.river == river]
        except (aiohttp.ClientError, TimeoutError, hydro.HydroParseError) as err:
            _LOGGER.warning("Unable to read the ARPAV hydrometric registry: %s", err)
            return self.async_abort(reason="cannot_connect")

        errors = {}
        if user_input is not None:
            order_text = user_input.get(CONF_HYDRO_ORDER, "").strip()
            ordered = ordered_selection(user_input[STEP_STATIONS], order_text, river)
            if not user_input[STEP_STATIONS]:
                errors["base"] = "no_stations"
            elif ordered is None:
                errors[CONF_HYDRO_ORDER] = "invalid_order"
            elif (ceilings := parse_ceilings(user_input.get(CONF_HYDRO_AXIS_CEILING), ordered)) is None:
                errors[CONF_HYDRO_AXIS_CEILING] = "invalid_axis_ceiling"
            else:
                by_id = {s.station_id: s for s in stations}
                known = {m["id"]: m for m in current}
                return self.async_create_entry(data={
                    CONF_HYDRO_STATIONS: [station_meta(by_id[i]) if i in by_id else known[i] for i in ordered],
                    CONF_HYDRO_AXIS_CEILING: ceilings,
                    CONF_HYDRO_ORDER: order_text,
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
            data_schema=_stations_schema(stations, [m["id"] for m in current], saved_order, extra),
            errors=errors,
            description_placeholders={"river": river, "stations": _order_hint(stations)},
        )
