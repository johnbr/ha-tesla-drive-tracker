"""Find cars and their sources in the entity registry."""
from __future__ import annotations

from collections.abc import Mapping

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .sources import FLEET, ROLES, TELEMETRY, Source, role_for, vin_of

PLATFORMS = frozenset({TELEMETRY, FLEET})

type Sources = dict[str, list[tuple[str, Source]]]


def find_cars(hass: HomeAssistant) -> dict[str, str]:
    """Every car a source platform knows about, as VIN to display name."""
    devices = dr.async_get(hass)
    cars: dict[str, str] = {}
    for entry in er.async_get(hass).entities.values():
        if entry.platform not in PLATFORMS:
            continue
        vin = vin_of(entry.unique_id)
        if vin is None:
            continue
        device = devices.async_get(entry.device_id) if entry.device_id else None
        name = device and (device.name_by_user or device.name)
        if name or vin not in cars:
            cars[vin] = name or vin
    return cars


def find_device_model(hass: HomeAssistant, vin: str) -> str | None:
    """The model a source integration reports for this car."""
    devices = dr.async_get(hass)
    for entry in er.async_get(hass).entities.values():
        if (
            entry.platform in PLATFORMS
            and entry.device_id
            and vin_of(entry.unique_id) == vin
        ):
            device = devices.async_get(entry.device_id)
            if device is not None and device.model:
                return device.model
    return None


def find_sources(
    hass: HomeAssistant, vin: str, overrides: Mapping[str, str] | None = None
) -> Sources:
    """The entities that can fill each role, with overrides replacing the rest."""
    sources: Sources = {}
    for entry in er.async_get(hass).entities.values():
        if entry.platform not in PLATFORMS or entry.disabled:
            continue
        for role, source in role_for(
            entry.platform, entry.domain, entry.unique_id, vin
        ):
            sources.setdefault(role, []).append((entry.entity_id, source))
    for role, entity_id in (overrides or {}).items():
        if role in ROLES:
            domain = entity_id.partition(".")[0]
            source = Source("", domain, "", ROLES[role][0].attribute)
            sources[role] = [(entity_id, source)]
    return sources
