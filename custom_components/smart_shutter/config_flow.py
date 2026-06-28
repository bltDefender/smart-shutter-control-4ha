"""Config flow and options flow for Smart Shutter Control."""
from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ANGLE_FULLY_CLOSED,
    CONF_ANGLE_HALF_CLOSED,
    CONF_COVER_ENTITY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
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
    DEFAULT_ANGLE_FULLY_CLOSED,
    DEFAULT_ANGLE_HALF_CLOSED,
    DEFAULT_POSITION_CLOSED,
    DEFAULT_POSITION_HALF,
    DEFAULT_POSITION_OPEN,
    DEFAULT_SUNSET_TYPE,
    DEFAULT_TEMP_THRESHOLD,
    DOMAIN,
)

# ── Selector helpers ──────────────────────────────────────────────────────


def _temp_sensor_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="sensor", multiple=True))


def _cover_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="cover"))


def _number(
    min_val: float, max_val: float, step: float = 1.0, unit: str = ""
) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_val,
            max=max_val,
            step=step,
            unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


def _select(options: list[dict]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


SUNSET_SELECT_OPTIONS = [
    {"value": "civil", "label": "Bürgerliche Dämmerung (−6°)"},
    {"value": "nautical", "label": "Nautische Dämmerung (−12°)"},
    {"value": "astronomical", "label": "Astronomische Dämmerung (−18°)"},
]


# ── Validation ────────────────────────────────────────────────────────────


def _validate_window(data: dict) -> dict[str, str]:
    """Validate per-window config; return mapping of field → error key."""
    errors: dict[str, str] = {}
    if not data.get(CONF_WINDOW_NAME, "").strip():
        errors[CONF_WINDOW_NAME] = "name_required"
    angle_closed = float(data.get(CONF_ANGLE_FULLY_CLOSED, DEFAULT_ANGLE_FULLY_CLOSED))
    angle_half = float(data.get(CONF_ANGLE_HALF_CLOSED, DEFAULT_ANGLE_HALF_CLOSED))
    if angle_closed >= angle_half:
        errors[CONF_ANGLE_HALF_CLOSED] = "angle_half_must_exceed_closed"
    return errors


# ── Schemas ───────────────────────────────────────────────────────────────


def _global_schema(lat: float = 48.0, lon: float = 9.0, defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_LATITUDE, default=d.get(CONF_LATITUDE, lat)): _number(
                -90, 90, 0.0001, "°"
            ),
            vol.Required(CONF_LONGITUDE, default=d.get(CONF_LONGITUDE, lon)): _number(
                -180, 180, 0.0001, "°"
            ),
            vol.Required(
                CONF_TEMP_SENSORS, default=d.get(CONF_TEMP_SENSORS, [])
            ): _temp_sensor_selector(),
            vol.Required(
                CONF_TEMP_THRESHOLD,
                default=d.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD),
            ): _number(0, 60, 0.5, "°C"),
            vol.Required(
                CONF_SUNSET_TYPE,
                default=d.get(CONF_SUNSET_TYPE, DEFAULT_SUNSET_TYPE),
            ): _select(SUNSET_SELECT_OPTIONS),
        }
    )


def _window_schema(defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_WINDOW_NAME, default=d.get(CONF_WINDOW_NAME, "")
            ): TextSelector(),
            vol.Required(
                CONF_WINDOW_ORIENTATION,
                default=d.get(CONF_WINDOW_ORIENTATION, 180.0),
            ): _number(0, 359, 1, "°"),
            vol.Required(
                CONF_COVER_ENTITY, default=d.get(CONF_COVER_ENTITY, "")
            ): _cover_selector(),
            vol.Optional(
                CONF_POSITION_OPEN,
                default=d.get(CONF_POSITION_OPEN, DEFAULT_POSITION_OPEN),
            ): _number(0, 100, 1, "%"),
            vol.Optional(
                CONF_POSITION_HALF,
                default=d.get(CONF_POSITION_HALF, DEFAULT_POSITION_HALF),
            ): _number(0, 100, 1, "%"),
            vol.Optional(
                CONF_POSITION_CLOSED,
                default=d.get(CONF_POSITION_CLOSED, DEFAULT_POSITION_CLOSED),
            ): _number(0, 100, 1, "%"),
            vol.Optional(
                CONF_ANGLE_FULLY_CLOSED,
                default=d.get(CONF_ANGLE_FULLY_CLOSED, DEFAULT_ANGLE_FULLY_CLOSED),
            ): _number(1, 90, 1, "°"),
            vol.Optional(
                CONF_ANGLE_HALF_CLOSED,
                default=d.get(CONF_ANGLE_HALF_CLOSED, DEFAULT_ANGLE_HALF_CLOSED),
            ): _number(1, 90, 1, "°"),
        }
    )


# ── Config flow ───────────────────────────────────────────────────────────


class SmartShutterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow (global settings only)."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            sensors: list[str] = user_input.get(CONF_TEMP_SENSORS, [])
            if not sensors:
                errors[CONF_TEMP_SENSORS] = "no_sensors"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Smart Shutter Control",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_global_schema(
                lat=self.hass.config.latitude,
                lon=self.hass.config.longitude,
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartShutterOptionsFlow:
        return SmartShutterOptionsFlow()


# ── Options flow ──────────────────────────────────────────────────────────


class SmartShutterOptionsFlow(config_entries.OptionsFlow):
    """Handle options: manage windows and global settings.

    Home Assistant guarantees that ``async_step_init`` is always called first,
    so ``self._windows`` is populated there (``self.config_entry`` is only
    available after the parent class initialises the flow, not in ``__init__``).
    """

    def __init__(self) -> None:
        self._windows: list[dict] = []
        self._editing_id: str | None = None

    # ── Menu ─────────────────────────────────────────────────────────────

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        merged = {**self.config_entry.data, **self.config_entry.options}
        self._windows = list(merged.get(CONF_WINDOWS, []))
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_window", "select_edit", "select_remove", "global_settings"],
        )

    # ── Global settings ───────────────────────────────────────────────────

    async def async_step_global_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        merged = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            sensors: list[str] = user_input.get(CONF_TEMP_SENSORS, [])
            if not sensors:
                errors[CONF_TEMP_SENSORS] = "no_sensors"
            else:
                new_opts = dict(self.config_entry.options)
                new_opts.update(user_input)
                new_opts[CONF_WINDOWS] = self._windows
                return self.async_create_entry(title="", data=new_opts)

        return self.async_show_form(
            step_id="global_settings",
            data_schema=_global_schema(
                lat=self.hass.config.latitude,
                lon=self.hass.config.longitude,
                defaults=merged,
            ),
            errors=errors,
        )

    # ── Add window ────────────────────────────────────────────────────────

    async def async_step_add_window(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_window(user_input)
            if not errors:
                window = {**user_input, CONF_WINDOW_ID: str(uuid.uuid4())}
                self._windows.append(window)
                new_opts = dict(self.config_entry.options)
                new_opts[CONF_WINDOWS] = self._windows
                return self.async_create_entry(title="", data=new_opts)

        return self.async_show_form(
            step_id="add_window",
            data_schema=_window_schema(),
            errors=errors,
        )

    # ── Select window for editing ─────────────────────────────────────────

    async def async_step_select_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if not self._windows:
            return self.async_abort(reason="no_windows")

        if user_input is not None:
            self._editing_id = user_input[CONF_WINDOW_ID]
            return await self.async_step_edit_window()

        options = [
            {"value": w[CONF_WINDOW_ID], "label": w.get(CONF_WINDOW_NAME, w[CONF_WINDOW_ID])}
            for w in self._windows
        ]
        return self.async_show_form(
            step_id="select_edit",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_WINDOW_ID): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )

    async def async_step_edit_window(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        current = next(
            (w for w in self._windows if w[CONF_WINDOW_ID] == self._editing_id), {}
        )

        if user_input is not None:
            errors = _validate_window(user_input)
            if not errors:
                updated = {**user_input, CONF_WINDOW_ID: self._editing_id}
                self._windows = [
                    updated if w[CONF_WINDOW_ID] == self._editing_id else w
                    for w in self._windows
                ]
                new_opts = dict(self.config_entry.options)
                new_opts[CONF_WINDOWS] = self._windows
                return self.async_create_entry(title="", data=new_opts)

        return self.async_show_form(
            step_id="edit_window",
            data_schema=_window_schema(current),
            errors=errors,
        )

    # ── Select window for removal ─────────────────────────────────────────

    async def async_step_select_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if not self._windows:
            return self.async_abort(reason="no_windows")

        if user_input is not None:
            remove_id = user_input[CONF_WINDOW_ID]
            self._windows = [
                w for w in self._windows if w[CONF_WINDOW_ID] != remove_id
            ]
            new_opts = dict(self.config_entry.options)
            new_opts[CONF_WINDOWS] = self._windows
            return self.async_create_entry(title="", data=new_opts)

        options = [
            {"value": w[CONF_WINDOW_ID], "label": w.get(CONF_WINDOW_NAME, w[CONF_WINDOW_ID])}
            for w in self._windows
        ]
        return self.async_show_form(
            step_id="select_remove",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_WINDOW_ID): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )
