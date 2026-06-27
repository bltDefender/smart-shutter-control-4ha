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
    TextSelectorConfig,
    TextSelectorType,
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
    SUNSET_OPTIONS,
)

# ── Selector helpers ────────────────────────────────────────────────────────


def _temp_sensor_selector() -> EntitySelector:
    return EntitySelector(
        EntitySelectorConfig(domain="sensor", multiple=True)
    )


def _cover_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="cover"))


def _number(min_val: float, max_val: float, step: float = 1.0, unit: str = "") -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_val,
            max=max_val,
            step=step,
            unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


def _select(options: list[str], translation_key: str | None = None) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=translation_key,
        )
    )


# ── Main config schema ──────────────────────────────────────────────────────

def _main_schema(hass_config: dict | None = None) -> vol.Schema:
    lat = hass_config.get("latitude", 48.0) if hass_config else 48.0
    lon = hass_config.get("longitude", 9.0) if hass_config else 9.0
    return vol.Schema(
        {
            vol.Required(CONF_LATITUDE, default=lat): _number(-90, 90, 0.0001, "°"),
            vol.Required(CONF_LONGITUDE, default=lon): _number(-180, 180, 0.0001, "°"),
            vol.Required(CONF_TEMP_SENSORS): _temp_sensor_selector(),
            vol.Required(CONF_TEMP_THRESHOLD, default=DEFAULT_TEMP_THRESHOLD): _number(
                0, 60, 0.5, "°C"
            ),
            vol.Required(CONF_SUNSET_TYPE, default=DEFAULT_SUNSET_TYPE): _select(
                SUNSET_OPTIONS
            ),
        }
    )


# ── Window schema ───────────────────────────────────────────────────────────

def _window_schema(defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_WINDOW_NAME, default=d.get(CONF_WINDOW_NAME, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(
                CONF_WINDOW_ORIENTATION, default=d.get(CONF_WINDOW_ORIENTATION, 180.0)
            ): _number(0, 359, 1, "°"),
            vol.Required(CONF_COVER_ENTITY, default=d.get(CONF_COVER_ENTITY, "")): _cover_selector(),
            vol.Optional(
                CONF_POSITION_OPEN, default=d.get(CONF_POSITION_OPEN, DEFAULT_POSITION_OPEN)
            ): _number(0, 100, 1, "%"),
            vol.Optional(
                CONF_POSITION_HALF, default=d.get(CONF_POSITION_HALF, DEFAULT_POSITION_HALF)
            ): _number(0, 100, 1, "%"),
            vol.Optional(
                CONF_POSITION_CLOSED, default=d.get(CONF_POSITION_CLOSED, DEFAULT_POSITION_CLOSED)
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


# ── Config flow ─────────────────────────────────────────────────────────────

class SmartShutterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(CONF_TEMP_SENSORS):
                errors[CONF_TEMP_SENSORS] = "no_sensors"
            else:
                return self.async_create_entry(
                    title="Smart Shutter Control",
                    data=user_input,
                )

        hass_cfg = {
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=_main_schema(hass_cfg),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> SmartShutterOptionsFlow:
        return SmartShutterOptionsFlow(config_entry)


# ── Options flow ─────────────────────────────────────────────────────────────

class SmartShutterOptionsFlow(config_entries.OptionsFlow):
    """Handle options: manage windows and global settings."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        # Work on a mutable copy so we can stage changes
        opts = dict(config_entry.options)
        cfg = dict(config_entry.data)
        self._windows: list[dict] = list(opts.get(CONF_WINDOWS, cfg.get(CONF_WINDOWS, [])))
        self._editing_id: str | None = None

    # ── Menu ──────────────────────────────────────────────────────────────

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_window", "select_edit", "select_remove", "global_settings"],
        )

    # ── Global settings ────────────────────────────────────────────────────

    async def async_step_global_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        merged = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            new_options = dict(self._config_entry.options)
            new_options.update(user_input)
            new_options[CONF_WINDOWS] = self._windows
            return self.async_create_entry(title="", data=new_options)

        defaults = {
            "latitude": merged.get(CONF_LATITUDE, self.hass.config.latitude),
            "longitude": merged.get(CONF_LONGITUDE, self.hass.config.longitude),
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=defaults["latitude"]): _number(-90, 90, 0.0001, "°"),
                vol.Required(CONF_LONGITUDE, default=defaults["longitude"]): _number(-180, 180, 0.0001, "°"),
                vol.Required(
                    CONF_TEMP_SENSORS, default=merged.get(CONF_TEMP_SENSORS, [])
                ): _temp_sensor_selector(),
                vol.Required(
                    CONF_TEMP_THRESHOLD,
                    default=merged.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD),
                ): _number(0, 60, 0.5, "°C"),
                vol.Required(
                    CONF_SUNSET_TYPE,
                    default=merged.get(CONF_SUNSET_TYPE, DEFAULT_SUNSET_TYPE),
                ): _select(SUNSET_OPTIONS),
            }
        )
        return self.async_show_form(
            step_id="global_settings",
            data_schema=schema,
            errors=errors,
        )

    # ── Add window ─────────────────────────────────────────────────────────

    async def async_step_add_window(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_window(user_input)
            if not errors:
                window = dict(user_input)
                window["id"] = str(uuid.uuid4())
                self._windows.append(window)
                new_options = dict(self._config_entry.options)
                new_options[CONF_WINDOWS] = self._windows
                return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="add_window",
            data_schema=_window_schema(),
            errors=errors,
        )

    # ── Select window for editing ──────────────────────────────────────────

    async def async_step_select_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if not self._windows:
            return self.async_abort(reason="no_windows")

        if user_input is not None:
            self._editing_id = user_input["window_id"]
            return await self.async_step_edit_window()

        options = [
            {"value": w["id"], "label": w.get(CONF_WINDOW_NAME, w["id"])}
            for w in self._windows
        ]
        return self.async_show_form(
            step_id="select_edit",
            data_schema=vol.Schema(
                {
                    vol.Required("window_id"): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )

    async def async_step_edit_window(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        current = next((w for w in self._windows if w["id"] == self._editing_id), {})

        if user_input is not None:
            errors = _validate_window(user_input)
            if not errors:
                updated = dict(user_input)
                updated["id"] = self._editing_id
                self._windows = [
                    updated if w["id"] == self._editing_id else w for w in self._windows
                ]
                new_options = dict(self._config_entry.options)
                new_options[CONF_WINDOWS] = self._windows
                return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="edit_window",
            data_schema=_window_schema(current),
            errors=errors,
        )

    # ── Select window for removal ──────────────────────────────────────────

    async def async_step_select_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if not self._windows:
            return self.async_abort(reason="no_windows")

        if user_input is not None:
            remove_id = user_input["window_id"]
            self._windows = [w for w in self._windows if w["id"] != remove_id]
            new_options = dict(self._config_entry.options)
            new_options[CONF_WINDOWS] = self._windows
            return self.async_create_entry(title="", data=new_options)

        options = [
            {"value": w["id"], "label": w.get(CONF_WINDOW_NAME, w["id"])}
            for w in self._windows
        ]
        return self.async_show_form(
            step_id="select_remove",
            data_schema=vol.Schema(
                {
                    vol.Required("window_id"): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )


def _validate_window(data: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not data.get(CONF_WINDOW_NAME, "").strip():
        errors[CONF_WINDOW_NAME] = "name_required"
    angle_closed = float(data.get(CONF_ANGLE_FULLY_CLOSED, DEFAULT_ANGLE_FULLY_CLOSED))
    angle_half = float(data.get(CONF_ANGLE_HALF_CLOSED, DEFAULT_ANGLE_HALF_CLOSED))
    if angle_closed >= angle_half:
        errors[CONF_ANGLE_HALF_CLOSED] = "angle_half_must_exceed_closed"
    return errors
