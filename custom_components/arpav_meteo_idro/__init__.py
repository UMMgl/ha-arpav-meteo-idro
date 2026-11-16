"""The Arpa Veneto Weather integration."""

import logging
from dataclasses import dataclass
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers import device_registry as dr

from .brightness_statistics import async_archive_brightness
from .coordinator import ArpaVenetoDataUpdateCoordinator

from .const import (
    CONF_ARCHIVE_BRIGHTNESS,
    CONF_ENTRY_TYPE,
    CONF_HYDRO_ARCHIVE,
    CONF_HYDRO_STATIONS,
    DOMAIN,
    ENTRY_TYPE_HYDRO,
)
from .hydro_coordinator import HydroCoordinator
from .hydro_statistics import async_import_hydro_history

_LOGGER = logging.getLogger(__name__)

# set up from the UI only: no YAML configuration
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Store the configuration in a dict for easy access
PLATFORMS = ["weather", "sensor"]
# a hydrometric entry has no weather entity
HYDRO_PLATFORMS = ["sensor"]

# The brightness batch is published around 09:30 standard time: this local hour
# is past it both in winter and in summer time
BRIGHTNESS_ARCHIVE_HOUR = 11
BRIGHTNESS_ARCHIVE_MINUTE = 15

# prefix of the device identifier of a station: (DOMAIN, f"hydro_{station_id}")
HYDRO_DEVICE_PREFIX = "hydro_"

# the station files cover the last 2-3 days: once a day is enough
HYDRO_ARCHIVE_HOUR = 3
HYDRO_ARCHIVE_MINUTE = 20

# Removed in 0.16.0: the manual station order saved by older hydrometric entries
# and the Repairs issue that announced its removal.
LEGACY_ORDER_OPTION = "display_order"
LEGACY_ORDER_REPAIR = "hydro_manual_order_deprecated"


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
    _async_remove_stale_hydro_devices(hass, entry, coordinator)

    if entry.options.get(CONF_HYDRO_ARCHIVE, True):
        _async_schedule_hydro_archive(hass, entry, coordinator)

    return True


def _hydro_device_station_id(device: dr.DeviceEntry) -> str | None:
    """Return the station a device of a hydrometric entry stands for."""
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and identifier.startswith(HYDRO_DEVICE_PREFIX):
            return identifier.removeprefix(HYDRO_DEVICE_PREFIX)
    return None


def _async_remove_stale_hydro_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: HydroCoordinator
) -> None:
    """Remove the devices of the stations the user deselected in the options."""
    selected = {meta["id"] for meta in coordinator.stations}
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        station_id = _hydro_device_station_id(device)
        if station_id is not None and station_id not in selected:
            _LOGGER.debug("Removing the device of the deselected station %s", station_id)
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Let the user delete the device of a station that is no longer selected."""
    if not _is_hydro(entry):
        return False
    station_id = _hydro_device_station_id(device)
    if station_id is None:
        return False
    selected = {meta["id"] for meta in entry.options.get(CONF_HYDRO_STATIONS, [])}
    return station_id not in selected


def _async_schedule_hydro_archive(hass: HomeAssistant, entry: ConfigEntry, coordinator):
    """Complete the level statistics once a day, and on startup."""

    async def archive(_now=None):
        try:
            await async_import_hydro_history(hass, coordinator)
        except HomeAssistantError as err:
            _LOGGER.warning("Unable to archive the hydrometric history: %s", err)

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an entry to the current version.

    Version 2 (0.16.0) removes the manual station order: the saved order is
    dropped, so a hydrometric entry shows its stations in the verified river
    order, with the stations outside a profile after them in selection order.
    The Repairs issue of the deprecation is deleted from the registry.
    """
    if entry.version > 2:
        # saved by a newer release: do not touch it
        return False

    if entry.version == 1:
        options = {k: v for k, v in entry.options.items() if k != LEGACY_ORDER_OPTION}
        ir.async_delete_issue(hass, DOMAIN, f"{LEGACY_ORDER_REPAIR}_{entry.entry_id}")
        hass.config_entries.async_update_entry(entry, options=options, version=2)
        _LOGGER.debug("Migrated the entry %s to version 2", entry.entry_id)
    return True


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

    async def handle_archive_hydro(call: ServiceCall) -> ServiceResponse:
        """Handle the service call to complete the hydrometric history."""
        sensors: dict[str, dict] = {}
        for coordinator in _called_coordinators(hass, call, HydroCoordinator):
            sensors.update(await async_import_hydro_history(hass, coordinator))
        return {"imported_hours": sum(s["hours"] for s in sensors.values()), "sensors": sensors}

    # Register the services
    hass.services.async_register(
        DOMAIN, "refresh_data", handle_refresh_data
    )
    hass.services.async_register(
        DOMAIN, "archive_brightness", handle_archive_brightness
    )
    hass.services.async_register(
        DOMAIN, "archive_hydro_history", handle_archive_hydro,
        supports_response=SupportsResponse.OPTIONAL,
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
