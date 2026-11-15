"""The Arpa Veneto Weather integration."""

import logging
from dataclasses import dataclass
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_track_time_change

from .brightness_statistics import async_archive_brightness
from .coordinator import ArpaVenetoDataUpdateCoordinator

from .const import (
    CONF_ARCHIVE_BRIGHTNESS,
    CONF_ENTRY_TYPE,
    CONF_HYDRO_ARCHIVE,
    DOMAIN,
    ENTRY_TYPE_HYDRO,
)
from .hydro_coordinator import HydroCoordinator
from .hydro_statistics import async_import_hydro_history

_LOGGER = logging.getLogger(__name__)

# Store the configuration in a dict for easy access
PLATFORMS = ["weather", "sensor"]
# a hydrometric entry has no weather entity
HYDRO_PLATFORMS = ["sensor"]

# The brightness batch is published around 09:30 standard time: this local hour
# is past it both in winter and in summer time
BRIGHTNESS_ARCHIVE_HOUR = 11
BRIGHTNESS_ARCHIVE_MINUTE = 15

# the station files cover the last 2-3 days: once a day is enough
HYDRO_ARCHIVE_HOUR = 3
HYDRO_ARCHIVE_MINUTE = 20


def _is_hydro(entry: ConfigEntry) -> bool:
    """Return True for a config entry of hydrometric stations."""
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HYDRO


@dataclass
class ArpavRuntimeData:
    """What a loaded config entry keeps at runtime."""

    coordinator: ArpaVenetoDataUpdateCoordinator | HydroCoordinator


def _platforms(entry: ConfigEntry) -> list[str]:
    return HYDRO_PLATFORMS if _is_hydro(entry) else PLATFORMS

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ARPA Veneto Weather from a config entry."""

    if _is_hydro(entry):
        return await _async_setup_hydro_entry(hass, entry)

    update_interval = timedelta(minutes=entry.options.get(
        "update_interval", 5))  # Fetch data every 5 minutes
    coordinator = ArpaVenetoDataUpdateCoordinator(
        hass,
        entry,
        update_interval,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ArpavRuntimeData(coordinator)

    # Reload when the options change
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    if entry.options.get(CONF_ARCHIVE_BRIGHTNESS):
        _async_schedule_brightness_archive(hass, entry, coordinator)

    # Forward the entry to the weather platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_setup_hydro_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the hydrometric stations of a river."""

    coordinator = HydroCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ArpavRuntimeData(coordinator)
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, HYDRO_PLATFORMS)

    if entry.options.get(CONF_HYDRO_ARCHIVE, True):
        _async_schedule_hydro_archive(hass, entry, coordinator)

    return True


def _async_schedule_hydro_archive(hass: HomeAssistant, entry: ConfigEntry, coordinator):
    """Complete the level statistics once a day, and on startup."""

    async def archive(_now=None):
        try:
            imported = await async_import_hydro_history(hass, coordinator)
        except HomeAssistantError as err:
            _LOGGER.warning("Unable to archive the hydrometric history: %s", err)
            return
        _LOGGER.debug("Imported %s hourly hydrometric statistics", imported)

    entry.async_on_unload(
        async_track_time_change(
            hass, archive, hour=HYDRO_ARCHIVE_HOUR, minute=HYDRO_ARCHIVE_MINUTE, second=0
        )
    )
    # the station files cover 2-3 days, so this recovers the time spent offline
    entry.async_create_background_task(hass, archive(), f"{DOMAIN}_archive_hydro_{entry.entry_id}")


def _async_schedule_brightness_archive(hass: HomeAssistant, entry: ConfigEntry, coordinator):
    """Archive the night sky brightness once a day, and on startup."""

    async def archive(_now=None):
        """Import the readings the API exposes as long-term statistics."""
        try:
            imported = await async_archive_brightness(
                hass, coordinator.latitude, coordinator.longitude)
        except (aiohttp.ClientError, TimeoutError, HomeAssistantError) as err:
            # a history archive is never worth failing a setup or an update for
            _LOGGER.warning("Unable to archive the night sky brightness: %s", err)
            return

        _LOGGER.debug("Archived %s hourly night sky brightness statistics", imported)

    entry.async_on_unload(
        async_track_time_change(
            hass,
            archive,
            hour=BRIGHTNESS_ARCHIVE_HOUR,
            minute=BRIGHTNESS_ARCHIVE_MINUTE,
            second=0,
        )
    )

    # the API exposes about 72 hours, so this recovers the days spent offline
    entry.async_create_background_task(hass, archive(), f"{DOMAIN}_archive_brightness")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload ARPA Veneto Weather config entry."""
    # the listeners registered with async_on_unload are removed by Home Assistant
    return await hass.config_entries.async_unload_platforms(entry, _platforms(entry))


async def async_setup(hass, config):
    """Register the service."""
    async def handle_refresh_data(call):
        """Handle the service call to refresh data."""
        for coordinator in _called_coordinators(hass, call):
            await coordinator.async_request_refresh()

    async def handle_archive_brightness(call):
        """Handle the service call to archive the night sky brightness."""
        for coordinator in _called_coordinators(hass, call, ArpaVenetoDataUpdateCoordinator):
            try:
                imported = await async_archive_brightness(
                    hass, coordinator.latitude, coordinator.longitude)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="archive_failed",
                    translation_placeholders={"error": str(err)}) from err
            _LOGGER.debug("Archived %s hourly night sky brightness statistics", imported)

    async def handle_archive_hydro(call):
        """Handle the service call to complete the hydrometric history."""
        for coordinator in _called_coordinators(hass, call, HydroCoordinator):
            imported = await async_import_hydro_history(hass, coordinator)
            _LOGGER.debug("Imported %s hourly hydrometric statistics", imported)

    # Register the services
    hass.services.async_register(
        DOMAIN, "refresh_data", handle_refresh_data
    )
    hass.services.async_register(
        DOMAIN, "archive_brightness", handle_archive_brightness
    )
    hass.services.async_register(
        DOMAIN, "archive_hydro_history", handle_archive_hydro
    )
    return True


def _called_coordinators(hass: HomeAssistant, call, kind=None):
    """Return the coordinators a service call is meant for."""

    loaded = {entry.entry_id: entry for entry in hass.config_entries.async_loaded_entries(DOMAIN)}
    entry_id = call.data.get("entry_id")
    if entry_id and entry_id not in loaded:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="entry_not_loaded",
            translation_placeholders={"entry_id": entry_id})
    # without an explicit entry, the call is meant for every entry
    entries = [loaded[entry_id]] if entry_id else list(loaded.values())
    coordinators = [entry.runtime_data.coordinator for entry in entries]
    if kind is not None:
        coordinators = [c for c in coordinators if isinstance(c, kind)]
        if entry_id and not coordinators:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="wrong_entry_type",
                translation_placeholders={"entry_id": entry_id})
    return coordinators

async def options_update_listener(hass: HomeAssistant, config: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config.entry_id)
