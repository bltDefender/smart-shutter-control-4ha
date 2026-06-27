"""Data coordinator for Smart Shutter Control."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ANGLE_FULLY_CLOSED,
    CONF_ANGLE_HALF_CLOSED,
    CONF_COVER_ENTITY,
    CONF_POSITION_CLOSED,
    CONF_POSITION_HALF,
    CONF_POSITION_OPEN,
    CONF_TEMP_SENSORS,
    CONF_TEMP_THRESHOLD,
    CONF_SUNSET_TYPE,
    CONF_WINDOWS,
    DEFAULT_ANGLE_FULLY_CLOSED,
    DEFAULT_ANGLE_HALF_CLOSED,
    DEFAULT_POSITION_CLOSED,
    DEFAULT_POSITION_HALF,
    DEFAULT_POSITION_OPEN,
    DEFAULT_SUNSET_TYPE,
    DEFAULT_TEMP_THRESHOLD,
    DOMAIN,
    SHUTTER_CLOSED,
    SHUTTER_HALF,
    SHUTTER_OPEN,
    SUNSET_ELEVATION,
    UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


def _compute_angle_diff(window_orientation: float, sun_azimuth: float) -> float:
    """Return the minimum angular distance (0–180°) between window normal and sun azimuth."""
    diff = abs(window_orientation - sun_azimuth) % 360
    return min(diff, 360.0 - diff)


def _compute_shutter_state(
    angle_diff: float,
    sun_elevation: float,
    avg_temp: float,
    temp_threshold: float,
    sunset_elevation: float,
    angle_fully_closed: float,
    angle_half_closed: float,
) -> str:
    """Return the desired shutter state given current conditions."""
    if sun_elevation <= sunset_elevation:
        return SHUTTER_OPEN
    if avg_temp < temp_threshold:
        return SHUTTER_OPEN
    if angle_diff < angle_fully_closed:
        return SHUTTER_CLOSED
    if angle_diff < angle_half_closed:
        return SHUTTER_HALF
    return SHUTTER_OPEN


class SmartShutterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages sun position tracking, temperature averaging, and shutter control."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.config_entry = config_entry
        # Track the last commanded state per window id to avoid redundant service calls
        self._commanded_states: dict[str, str] = {}
        self._unsub_listeners: list = []

    async def async_setup(self) -> None:
        """Register state-change listeners."""
        merged = {**self.config_entry.data, **self.config_entry.options}
        temp_sensors: list[str] = merged.get(CONF_TEMP_SENSORS, [])

        watch_entities = ["sun.sun"] + temp_sensors
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, watch_entities, self._on_state_change
            )
        )

    async def async_teardown(self) -> None:
        """Unregister all listeners."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    @callback
    def _on_state_change(self, event) -> None:  # noqa: ANN001
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch sun + temperature data, compute and apply shutter states."""
        merged = {**self.config_entry.data, **self.config_entry.options}

        # --- Sun ---
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            raise UpdateFailed("sun.sun entity not found – is the sun integration loaded?")

        sun_azimuth = float(sun_state.attributes.get("azimuth", 0.0))
        sun_elevation = float(sun_state.attributes.get("elevation", -90.0))

        # --- Temperature ---
        temp_sensors: list[str] = merged.get(CONF_TEMP_SENSORS, [])
        temps: list[float] = []
        for sensor_id in temp_sensors:
            state = self.hass.states.get(sensor_id)
            if state and state.state not in ("unknown", "unavailable", "none"):
                try:
                    temps.append(float(state.state))
                except ValueError:
                    _LOGGER.warning("Could not parse temperature from %s: %s", sensor_id, state.state)

        avg_temp = sum(temps) / len(temps) if temps else 0.0

        temp_threshold: float = merged.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD)
        sunset_type: str = merged.get(CONF_SUNSET_TYPE, DEFAULT_SUNSET_TYPE)
        sunset_elev: float = SUNSET_ELEVATION[sunset_type]

        is_daytime = sun_elevation > sunset_elev
        temp_active = avg_temp >= temp_threshold

        # --- Windows ---
        windows: list[dict] = merged.get(CONF_WINDOWS, [])
        window_data: dict[str, dict[str, Any]] = {}

        for win in windows:
            wid = win["id"]
            orientation = float(win.get("orientation", 180.0))
            angle_fully_closed = float(win.get(CONF_ANGLE_FULLY_CLOSED, DEFAULT_ANGLE_FULLY_CLOSED))
            angle_half_closed = float(win.get(CONF_ANGLE_HALF_CLOSED, DEFAULT_ANGLE_HALF_CLOSED))

            angle_diff = _compute_angle_diff(orientation, sun_azimuth)

            desired = _compute_shutter_state(
                angle_diff=angle_diff,
                sun_elevation=sun_elevation,
                avg_temp=avg_temp,
                temp_threshold=temp_threshold,
                sunset_elevation=sunset_elev,
                angle_fully_closed=angle_fully_closed,
                angle_half_closed=angle_half_closed,
            )

            await self._apply_shutter_state(wid, desired, win)

            window_data[wid] = {
                "name": win.get("name", wid),
                "state": desired,
                "orientation": orientation,
                "angle_diff": round(angle_diff, 1),
                "sun_azimuth": round(sun_azimuth, 1),
                "sun_elevation": round(sun_elevation, 1),
                "temperature": round(avg_temp, 1),
                "temp_threshold": temp_threshold,
                "angle_fully_closed": angle_fully_closed,
                "angle_half_closed": angle_half_closed,
                "is_daytime": is_daytime,
                "temp_active": temp_active,
                "automation_active": is_daytime and temp_active,
            }

        return {
            "sun_azimuth": round(sun_azimuth, 1),
            "sun_elevation": round(sun_elevation, 1),
            "temperature": round(avg_temp, 1),
            "temp_threshold": temp_threshold,
            "is_daytime": is_daytime,
            "temp_active": temp_active,
            "windows": window_data,
        }

    async def _apply_shutter_state(
        self, window_id: str, desired: str, win_cfg: dict
    ) -> None:
        """Call cover service if the desired state differs from the last commanded state."""
        if self._commanded_states.get(window_id) == desired:
            return

        cover_entity = win_cfg.get(CONF_COVER_ENTITY)
        if not cover_entity:
            return

        if desired == SHUTTER_OPEN:
            position = int(win_cfg.get(CONF_POSITION_OPEN, DEFAULT_POSITION_OPEN))
        elif desired == SHUTTER_HALF:
            position = int(win_cfg.get(CONF_POSITION_HALF, DEFAULT_POSITION_HALF))
        else:
            position = int(win_cfg.get(CONF_POSITION_CLOSED, DEFAULT_POSITION_CLOSED))

        try:
            await self.hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": cover_entity, "position": position},
                blocking=False,
            )
            self._commanded_states[window_id] = desired
            _LOGGER.info(
                "Window '%s': state → %s (position %d)",
                win_cfg.get("name", window_id),
                desired,
                position,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Window '%s': failed to set position %d – %s",
                win_cfg.get("name", window_id),
                position,
                err,
            )
