"""Add a car, and choose where its figures come from."""
from __future__ import annotations

from typing import Any

import probatio

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CAR_COLOR,
    CONF_CAR_MODEL,
    CONF_ROLES,
    CONF_THRESHOLDS,
    CONF_VIN,
    DOMAIN,
)
from .coordinator import DriveConfigEntry
from .engine import DEFAULT_THRESHOLDS
from .reading import MODELS, number
from .resolver import find_cars
from .sources import (
    ROLE_CAR_TYPE,
    ROLE_DESTINATION,
    ROLE_HEADING,
    ROLE_PAINT,
    ROLE_POSITION,
    ROLE_ROOF,
    ROLE_ROUTE_LINE,
    ROLES,
)

MAX_THRESHOLD_MINUTES = 120

TRACKER_ROLES = frozenset({ROLE_POSITION, ROLE_DESTINATION})
# These come from an attribute of a specific entity, so another entity can't serve.
FIXED_ROLES = frozenset(
    {ROLE_HEADING, ROLE_ROUTE_LINE, ROLE_PAINT, ROLE_ROOF, ROLE_CAR_TYPE}
)


def _thresholds(values: list[str]) -> list[float] | None:
    """The chosen minutes, largest first, or ``None`` if any is unusable."""
    minutes = [number(value) for value in values]
    if not minutes or any(
        value is None or not 0 < value <= MAX_THRESHOLD_MINUTES for value in minutes
    ):
        return None
    return sorted(set(minutes), reverse=True)


class DriveTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick a car one of the source integrations already knows."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(entry: DriveConfigEntry) -> DriveTrackerOptionsFlow:
        return DriveTrackerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        cars = find_cars(self.hass)
        if user_input is not None:
            vin = user_input[CONF_VIN]
            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=cars.get(vin, vin), data={CONF_VIN: vin}
            )

        configured = {entry.unique_id for entry in self._async_current_entries()}
        available = {
            vin: name for vin, name in cars.items() if vin not in configured
        }
        if not available:
            return self.async_abort(reason="no_cars")
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_VIN): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=vin, label=f"{name} (…{vin[-6:]})"
                                )
                                for vin, name in available.items()
                            ]
                        )
                    )
                }
            ),
        )


class DriveTrackerOptionsFlow(OptionsFlowWithReload):
    """Arrival thresholds, and a source of your own for any role."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            thresholds = _thresholds(user_input[CONF_THRESHOLDS])
            if thresholds is None:
                errors[CONF_THRESHOLDS] = "invalid_thresholds"
            else:
                roles = {
                    role: user_input[role]
                    for role in ROLES
                    if user_input.get(role)
                }
                look = {
                    key: user_input[key]
                    for key in (CONF_CAR_MODEL, CONF_CAR_COLOR)
                    if user_input.get(key)
                }
                return self.async_create_entry(
                    data={CONF_THRESHOLDS: thresholds, CONF_ROLES: roles, **look}
                )

        options = self.config_entry.options
        chosen = options.get(CONF_THRESHOLDS, DEFAULT_THRESHOLDS)
        schema: dict[Any, Any] = {
            probatio.Required(
                CONF_THRESHOLDS, default=[f"{value:g}" for value in chosen]
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["2", "5", "10", "15"], multiple=True, custom_value=True
                )
            )
        }
        schema[
            probatio.Optional(
                CONF_CAR_MODEL,
                description={"suggested_value": options.get(CONF_CAR_MODEL)},
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=sorted(MODELS), translation_key=CONF_CAR_MODEL
            )
        )
        schema[
            probatio.Optional(
                CONF_CAR_COLOR,
                description={"suggested_value": options.get(CONF_CAR_COLOR)},
            )
        ] = selector.TextSelector()
        roles = options.get(CONF_ROLES, {})
        for role in ROLES:
            if role in FIXED_ROLES:
                continue
            domain = "device_tracker" if role in TRACKER_ROLES else None
            schema[
                probatio.Optional(
                    role, description={"suggested_value": roles.get(role)}
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=domain)
                if domain
                else selector.EntitySelectorConfig()
            )
        return self.async_show_form(
            step_id="init", data_schema=probatio.Schema(schema), errors=errors
        )
