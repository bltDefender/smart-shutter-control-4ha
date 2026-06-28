"""Smart Shutter Control – Home Assistant integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, PLATFORMS
from .coordinator import SmartShutterCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_FORCE_UPDATE = "force_update"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Shutter from a config entry."""
    coordinator = SmartShutterCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register the force_update service once (idempotent: HA ignores re-registration).
    if not hass.services.has_service(DOMAIN, SERVICE_FORCE_UPDATE):

        async def _handle_force_update(call: ServiceCall) -> None:  # noqa: ARG001
            """Re-send shutter commands for all configured windows."""
            for coordinator in hass.data.get(DOMAIN, {}).values():
                if isinstance(coordinator, SmartShutterCoordinator):
                    await coordinator.async_force_update()

        hass.services.async_register(DOMAIN, SERVICE_FORCE_UPDATE, _handle_force_update)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: SmartShutterCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_teardown()

    # Remove the service when the last entry is unloaded.
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_FORCE_UPDATE)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change (e.g. windows added or removed)."""
    await hass.config_entries.async_reload(entry.entry_id)
