"""Data coordinator for Smart Shutter Control."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ANGLE_FULLY_CLOSED,
    CONF_ANGLE_HALF_CLOSED,
    CONF_CONTROL_MODE,
    CONF_COVER_ENTITY,
    CONF_CUSTOM_COMMAND_FIELD,
    CONF_CUSTOM_COMMAND_TEMPLATE,
    CONF_CUSTOM_SERVICE,
    CONF_CUSTOM_TARGET_FIELD,
    CONF_POSITION_CLOSED,
    CONF_POSITION_HALF,
    CONF_POSITION_OPEN,
    CONF_SUNSET_TYPE,
    CONF_TEMP_SENSORS,
    CONF_TEMP_THRESHOLD,
    CONF_WINDOW_ID,
    CONF_WINDOW_NAME,
    CONF_WINDOW_ORIENTATION,
    CONF_WINDOWS,
    CONTROL_MODE_CUSTOM,
    DEFAULT_CONTROL_MODE,
    DEFAULT_ANGLE_FULLY_CLOSED,
    DEFAULT_ANGLE_HALF_CLOSED,
    DEFAULT_CUSTOM_COMMAND_FIELD,
    DEFAULT_CUSTOM_COMMAND_TEMPLATE,
    DEFAULT_CUSTOM_SERVICE,
    DEFAULT_CUSTOM_TARGET_FIELD,
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


# ── Pure calculation helpers ──────────────────────────────────────────────


def _angle_diff(window_orientation: float, sun_azimuth: float) -> float:
    """Return the minimum angular distance (0–180°) between two compass bearings."""
    diff = abs(window_orientation - sun_azimuth) % 360.0
    return min(diff, 360.0 - diff)


def _desired_shutter_state(
    *,
    angle_diff: float,
    sun_elevation: float,
    avg_temp: float,
    temp_threshold: float,
    sunset_elevation: float,
    angle_fully_closed: float,
    angle_half_closed: float,
) -> str:
    """Return the desired shutter state for a single window.

    Priority (highest first):
    1. Night / below sunset elevation → always open.
    2. Temperature below threshold → always open.
    3. Sun directly facing window (angle < fully-closed zone) → closed.
    4. Sun at oblique angle (angle < half-closed zone) → half closed.
    5. Otherwise → open.
    """
    if sun_elevation <= sunset_elevation:
        return SHUTTER_OPEN
    if avg_temp < temp_threshold:
        return SHUTTER_OPEN
    if angle_diff < angle_fully_closed:
        return SHUTTER_CLOSED
    if angle_diff < angle_half_closed:
        return SHUTTER_HALF
    return SHUTTER_OPEN


# ── Coordinator ───────────────────────────────────────────────────────────


class SmartShutterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage sun/temperature polling and per-window shutter control."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.config_entry = config_entry
        # Track the last commanded state per window id to avoid redundant calls.
        self._commanded_states: dict[str, str] = {}
        self._unsub_listeners: list = []

    async def async_setup(self) -> None:
        """Register state-change listeners for sun and temperature sensors."""
        merged = {**self.config_entry.data, **self.config_entry.options}
        temp_sensors: list[str] = merged.get(CONF_TEMP_SENSORS, [])

        watch_entities = ["sun.sun"] + temp_sensors
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, watch_entities, self._on_state_change
            )
        )

    async def async_teardown(self) -> None:
        """Unregister all state-change listeners."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    async def async_force_update(self) -> None:
        """Clear the commanded-state cache and immediately re-apply all shutter states.

        This causes every window to resend its cover command regardless of whether
        the state has changed, which is useful for debugging (e.g. to verify MQTT
        commands on the broker).
        """
        self._commanded_states.clear()
        await self.async_request_refresh()

    @callback
    def _on_state_change(self, event: Any) -> None:
        """Trigger a coordinator refresh when a tracked entity changes."""
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch sun + temperature, compute and apply shutter states."""
        merged = {**self.config_entry.data, **self.config_entry.options}

        # ── Sun ──────────────────────────────────────────────────────────
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            raise UpdateFailed(
                "sun.sun entity not found – make sure the 'sun' integration is loaded."
            )

        sun_azimuth = float(sun_state.attributes.get("azimuth", 0.0))
        sun_elevation = float(sun_state.attributes.get("elevation", -90.0))

        # ── Temperature ───────────────────────────────────────────────────
        temp_sensors: list[str] = merged.get(CONF_TEMP_SENSORS, [])
        temps: list[float] = []
        for sensor_id in temp_sensors:
            state = self.hass.states.get(sensor_id)
            if state and state.state not in ("unknown", "unavailable", "none"):
                try:
                    temps.append(float(state.state))
                except ValueError:
                    _LOGGER.warning(
                        "Cannot parse temperature from %s: %r", sensor_id, state.state
                    )

        avg_temp = sum(temps) / len(temps) if temps else 0.0
        temp_threshold: float = float(merged.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD))
        sunset_type: str = merged.get(CONF_SUNSET_TYPE, DEFAULT_SUNSET_TYPE)
        sunset_elev: float = SUNSET_ELEVATION[sunset_type]

        is_daytime = sun_elevation > sunset_elev
        temp_active = avg_temp >= temp_threshold

        # ── Windows ───────────────────────────────────────────────────────
        windows: list[dict] = merged.get(CONF_WINDOWS, [])
        window_data: dict[str, dict[str, Any]] = {}

        for win in windows:
            wid: str = win[CONF_WINDOW_ID]
            orientation = float(win.get(CONF_WINDOW_ORIENTATION, 180.0))
            angle_fc = float(win.get(CONF_ANGLE_FULLY_CLOSED, DEFAULT_ANGLE_FULLY_CLOSED))
            angle_hc = float(win.get(CONF_ANGLE_HALF_CLOSED, DEFAULT_ANGLE_HALF_CLOSED))
            diff = _angle_diff(orientation, sun_azimuth)

            desired = _desired_shutter_state(
                angle_diff=diff,
                sun_elevation=sun_elevation,
                avg_temp=avg_temp,
                temp_threshold=temp_threshold,
                sunset_elevation=sunset_elev,
                angle_fully_closed=angle_fc,
                angle_half_closed=angle_hc,
            )

            await self._apply_shutter_state(wid, desired, win)

            window_data[wid] = {
                "name": win.get(CONF_WINDOW_NAME, wid),
                "state": desired,
                "orientation": orientation,
                "angle_diff": round(diff, 1),
                "sun_azimuth": round(sun_azimuth, 1),
                "sun_elevation": round(sun_elevation, 1),
                "temperature": round(avg_temp, 1),
                "temp_threshold": temp_threshold,
                "angle_fully_closed": angle_fc,
                "angle_half_closed": angle_hc,
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
        """Send a cover service call only when the state has actually changed."""
        if self._commanded_states.get(window_id) == desired:
            return

        cover_entity: str | None = win_cfg.get(CONF_COVER_ENTITY)
        if not cover_entity:
            return

        position_map = {
            SHUTTER_OPEN: int(win_cfg.get(CONF_POSITION_OPEN, DEFAULT_POSITION_OPEN)),
            SHUTTER_HALF: int(win_cfg.get(CONF_POSITION_HALF, DEFAULT_POSITION_HALF)),
            SHUTTER_CLOSED: int(win_cfg.get(CONF_POSITION_CLOSED, DEFAULT_POSITION_CLOSED)),
        }
        position = position_map[desired]
        name = win_cfg.get(CONF_WINDOW_NAME, window_id)

        control_mode = win_cfg.get(CONF_CONTROL_MODE, DEFAULT_CONTROL_MODE)

        try:
            if control_mode == CONTROL_MODE_CUSTOM:
                custom_service: str = win_cfg.get(CONF_CUSTOM_SERVICE, DEFAULT_CUSTOM_SERVICE)
                if "." not in custom_service:
                    raise ValueError(f"Invalid custom service '{custom_service}'")
                service_domain, service_name = custom_service.split(".", 1)
                command_template: str = win_cfg.get(
                    CONF_CUSTOM_COMMAND_TEMPLATE, DEFAULT_CUSTOM_COMMAND_TEMPLATE
                )
                command = command_template.format(
                    position=position,
                    state=desired,
                    entity_id=cover_entity,
                )
                command_field = (
                    win_cfg.get(CONF_CUSTOM_COMMAND_FIELD, DEFAULT_CUSTOM_COMMAND_FIELD)
                    or DEFAULT_CUSTOM_COMMAND_FIELD
                )
                target_field = win_cfg.get(CONF_CUSTOM_TARGET_FIELD, DEFAULT_CUSTOM_TARGET_FIELD)
                service_data: dict[str, Any] = {command_field: command}
                if target_field:
                    service_data[target_field] = cover_entity
                await self.hass.services.async_call(
                    service_domain,
                    service_name,
                    service_data,
                    blocking=False,
                )
            else:
                await self.hass.services.async_call(
                    "cover",
                    "set_cover_position",
                    {"entity_id": cover_entity, "position": position},
                    blocking=False,
                )
            self._commanded_states[window_id] = desired
            _LOGGER.info(
                "Window '%s': %s → position %d", name, desired, position
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Window '%s': failed to set position %d – %s", name, position, err
            )
