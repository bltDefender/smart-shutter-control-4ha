"""Sensor platform for Smart Shutter Control."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_WINDOWS, DOMAIN, SHUTTER_CLOSED, SHUTTER_HALF, SHUTTER_OPEN
from .coordinator import SmartShutterCoordinator

STATE_ICONS = {
    SHUTTER_OPEN: "mdi:window-shutter-open",
    SHUTTER_HALF: "mdi:window-shutter-alert",
    SHUTTER_CLOSED: "mdi:window-shutter",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: SmartShutterCoordinator = hass.data[DOMAIN][entry.entry_id]
    merged = {**entry.data, **entry.options}
    windows = merged.get(CONF_WINDOWS, [])

    entities: list[SensorEntity] = [SmartShutterGlobalSensor(coordinator, entry)]
    for win in windows:
        entities.append(SmartShutterWindowSensor(coordinator, entry, win["id"]))

    async_add_entities(entities, update_before_add=True)


class SmartShutterGlobalSensor(CoordinatorEntity[SmartShutterCoordinator], SensorEntity):
    """Global sensor showing sun position and temperature."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, coordinator: SmartShutterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_global"
        self._attr_name = "Sonnenstand"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        elev = self.coordinator.data.get("sun_elevation", 0)
        return "Tag" if self.coordinator.data.get("is_daytime") else "Nacht"

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        d = self.coordinator.data
        return {
            "sun_azimuth": d.get("sun_azimuth"),
            "sun_elevation": d.get("sun_elevation"),
            "temperature": d.get("temperature"),
            "temp_threshold": d.get("temp_threshold"),
            "is_daytime": d.get("is_daytime"),
            "temp_active": d.get("temp_active"),
        }


class SmartShutterWindowSensor(CoordinatorEntity[SmartShutterCoordinator], SensorEntity):
    """Per-window sensor exposing shutter state and all data needed by the Lovelace card."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartShutterCoordinator,
        entry: ConfigEntry,
        window_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._window_id = window_id
        self._attr_unique_id = f"{entry.entry_id}_{window_id}"

    def _window_data(self) -> dict:
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("windows", {}).get(self._window_id, {})

    @property
    def name(self) -> str:
        return self._window_data().get("name", self._window_id)

    @property
    def native_value(self) -> str | None:
        return self._window_data().get("state")

    @property
    def icon(self) -> str:
        state = self._window_data().get("state", SHUTTER_OPEN)
        return STATE_ICONS.get(state, "mdi:window-shutter-open")

    @property
    def extra_state_attributes(self) -> dict:
        d = self._window_data()
        if not d:
            return {}
        return {
            "window_orientation": d.get("orientation"),
            "sun_azimuth": d.get("sun_azimuth"),
            "sun_elevation": d.get("sun_elevation"),
            "sun_angle_diff": d.get("angle_diff"),
            "temperature": d.get("temperature"),
            "temp_threshold": d.get("temp_threshold"),
            "angle_fully_closed": d.get("angle_fully_closed"),
            "angle_half_closed": d.get("angle_half_closed"),
            "is_daytime": d.get("is_daytime"),
            "temp_active": d.get("temp_active"),
            "automation_active": d.get("automation_active"),
        }
