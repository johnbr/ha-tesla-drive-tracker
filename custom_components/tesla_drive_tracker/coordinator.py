"""Follow one car's sources and publish what the rule modules make of them.

Nothing here polls the car. Source state changes drive it, and the coordinator's
interval is the clock the trip engine needs for a car that has gone quiet.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_HOME,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DistanceConverter, SpeedConverter

from .const import (
    CONF_CAR_COLOR,
    CONF_CAR_MODEL,
    CONF_ROLES,
    CONF_THRESHOLDS,
    CONF_VIN,
    DOMAIN,
    LOGGER,
    RESOLVE_COOLDOWN_SECONDS,
    SAVE_EVERY_SECONDS,
    STORAGE_VERSION,
    TICK_SECONDS,
)
from .engine import (
    DEFAULT_THRESHOLDS,
    EVENT_DRIVE_ENDED,
    EVENT_DRIVE_STARTED,
    DriveEvent,
    TripEngine,
    is_home,
)
from .pairing import (
    STATUS_PAIRED,
    DestinationFix,
    DestinationPairing,
)
from .privacy import is_hidden, redact_event
from .reading import build_reading, car_model, number, stream_silent
from .resolver import PLATFORMS, Sources, find_device_model, find_sources
from .route_line import RouteLine, parse_route_line
from .sources import (
    ROLE_ARRIVAL_BATTERY,
    ROLE_BATTERY,
    ROLE_CAR_TYPE,
    ROLE_DESTINATION,
    ROLE_DISTANCE,
    ROLE_GEAR,
    ROLE_HEADING,
    ROLE_ODOMETER,
    ROLE_PAINT,
    ROLE_POSITION,
    ROLE_ROOF,
    ROLE_ROUTE_LINE,
    ROLE_SPEED,
    ROLE_TRAFFIC_DELAY,
    ROLES,
    Sample,
    Source,
    pick,
    pick_sample,
)
from .trail import Trail
from .view import DriveView, build_view

type DriveConfigEntry = ConfigEntry[DriveCoordinator]
type EventListener = Callable[[DriveEvent], None]

# The engine works in miles. A source shows whatever the owner's unit system says.
ROLE_UNITS = {
    ROLE_SPEED: (SpeedConverter, UnitOfSpeed.MILES_PER_HOUR),
    ROLE_ODOMETER: (DistanceConverter, UnitOfLength.MILES),
    ROLE_DISTANCE: (DistanceConverter, UnitOfLength.MILES),
}


def _in_engine_units(role: str, value: Any, unit: str | None) -> Any:
    if role not in ROLE_UNITS or unit is None:
        return value
    converter, target = ROLE_UNITS[role]
    amount = number(value)
    if amount is None:
        return value
    try:
        return converter.convert(amount, unit, target)
    except HomeAssistantError:
        return None


def _store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


async def async_remove_storage(hass: HomeAssistant, entry_id: str) -> None:
    """Delete a removed car's trail and trip memory."""
    await _store(hass, entry_id).async_remove()


class DriveCoordinator(DataUpdateCoordinator[DriveView]):
    """Runs the trip engine for one car."""

    config_entry: DriveConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: DriveConfigEntry,
        started_at: Callable[[], float],
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=TICK_SECONDS),
        )
        self.vin: str = entry.data[CONF_VIN]
        self.sources: Sources = {}
        self.trail = Trail()
        self.hidden = False
        self.last_trip: dict[str, Any] | None = None
        self.closers: set[CALLBACK_TYPE] = set()
        self._started_at = started_at
        self._thresholds = tuple(
            entry.options.get(CONF_THRESHOLDS, DEFAULT_THRESHOLDS)
        )
        self._engine = TripEngine(self._thresholds)
        self._pairing = DestinationPairing()
        self._store = _store(hass, entry.entry_id)
        self._saved_at = 0.0
        self._event_listeners: list[EventListener] = []
        self._device_model: str | None = None
        self._route_text: str | None = None
        self._route_line = RouteLine()
        self._resolver = Debouncer(
            hass,
            LOGGER,
            cooldown=RESOLVE_COOLDOWN_SECONDS,
            immediate=False,
            function=self._async_check_sources,
        )

    async def _async_setup(self) -> None:
        stored = await self._store.async_load() or {}
        if "engine" in stored:
            self._engine = TripEngine.from_dict(stored["engine"], self._thresholds)
        if "pairing" in stored:
            self._pairing = DestinationPairing.from_dict(stored["pairing"])
        self.hidden = is_hidden(stored.get("hide", "off"))
        self.last_trip = stored.get("last_trip")
        self.trail = Trail([tuple(point) for point in stored.get("trail", [])])

        self.sources = self._resolve()
        self._device_model = find_device_model(self.hass, self.vin)
        self._report_sources()
        entity_ids = {
            entity_id
            for candidates in self.sources.values()
            for entity_id, _ in candidates
        }
        self.config_entry.async_on_unload(
            async_track_state_change_event(
                self.hass, entity_ids, self._on_source_change
            )
        )
        self.config_entry.async_on_unload(
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_registry_update
            )
        )
        self.config_entry.async_on_unload(self._resolver.async_shutdown)

    async def _async_update_data(self) -> DriveView:
        return self._compute()

    def _resolve(self) -> Sources:
        return find_sources(
            self.hass, self.vin, self.config_entry.options.get(CONF_ROLES)
        )

    def _report_sources(self) -> None:
        """Say so when nothing can tell whether this car is driving."""
        issue = f"no_sources_{self.config_entry.entry_id}"
        if ROLE_SPEED in self.sources or ROLE_GEAR in self.sources:
            ir.async_delete_issue(self.hass, DOMAIN, issue)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="no_sources",
            translation_placeholders={"name": self.config_entry.title},
        )

    @callback
    def _on_source_change(self, event: Event) -> None:
        self.async_set_updated_data(self._compute())

    @callback
    def _on_registry_update(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Notice a signal added to the car, or a source renamed or removed."""
        entry = er.async_get(self.hass).async_get(event.data["entity_id"])
        if entry is None or entry.platform in PLATFORMS:
            self._resolver.async_schedule_call()

    async def _async_check_sources(self) -> None:
        """Reload for new sources, because a new role can add entities."""
        if self._resolve() != self.sources:
            self.hass.config_entries.async_schedule_reload(
                self.config_entry.entry_id
            )

    def _samples(self, role: str) -> list[tuple[Source, Sample]]:
        samples = []
        for entity_id, source in self.sources.get(role, ()):
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            value = state.state
            if source.attribute is not None:
                value = state.attributes.get(source.attribute, value)
            sample = Sample(
                _in_engine_units(
                    role, value, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                ),
                state.last_reported_timestamp,
                number(state.attributes.get(ATTR_LATITUDE)),
                number(state.attributes.get(ATTR_LONGITUDE)),
            )
            samples.append((source, sample))
        return samples

    def _fix(self, sample: Sample | None, now: float) -> DestinationFix:
        """Pair what the car says, then give a route home the home zone."""
        fix = self._pairing.update(
            sample and sample.value,
            sample and sample.latitude,
            sample and sample.longitude,
            now,
            hidden=self.hidden,
        )
        home = self.hass.states.get("zone.home")
        if fix.name and is_home(fix.name) and home is not None:
            return DestinationFix(
                STATUS_PAIRED,
                fix.name,
                home.attributes.get(ATTR_LATITUDE),
                home.attributes.get(ATTR_LONGITUDE),
            )
        return fix

    def _route(self, text: Any) -> RouteLine:
        """The decoded line, kept until the car sends a different one."""
        if text != self._route_text:
            self._route_text = text
            self._route_line = parse_route_line(text)
        return self._route_line

    def _compute(self) -> DriveView:
        now = dt_util.utcnow().timestamp()
        started_at = self._started_at()
        values = {
            role: pick(self._samples(role), now, started_at) for role in ROLES
        }
        speed = pick_sample(self._samples(ROLE_SPEED), now, started_at)
        gear = pick_sample(self._samples(ROLE_GEAR), now, started_at)
        if stream_silent(
            values[ROLE_SPEED],
            speed and speed.reported_at,
            values[ROLE_GEAR],
            gear and gear.reported_at,
            now,
        ):
            values[ROLE_SPEED] = values[ROLE_GEAR] = None
        reading = build_reading(
            values,
            now,
            at_home=(
                None
                if values[ROLE_POSITION] is None
                else values[ROLE_POSITION] == STATE_HOME
            ),
            travelled=self._travelled(),
        )
        events = self._engine.update(reading)
        fix = self._fix(
            pick_sample(self._samples(ROLE_DESTINATION), now, started_at), now
        )

        # Where a parked car was left is still where it is after a restart, facing
        # the same way with the same charge. A parked car doesn't repeat these, and
        # they feed only the display, never the engine.
        position = pick_sample(self._samples(ROLE_POSITION), now, 0)
        heading = pick(self._samples(ROLE_HEADING), now, 0)
        battery = pick(self._samples(ROLE_BATTERY), now, 0)
        located = position is not None and position.latitude is not None
        for event in events:
            self._on_event(event)
        if (
            located
            and self._engine.trip is not None
            and values[ROLE_POSITION] is not None
        ):
            self.trail.add(position.latitude, position.longitude, now)

        view = build_view(
            self._engine,
            fix=fix,
            hidden=self.hidden,
            now=now,
            minutes=reading.minutes_to_arrival,
            distance=number(values[ROLE_DISTANCE]),
            arrival_battery=number(values[ROLE_ARRIVAL_BATTERY]),
            traffic_delay=number(values[ROLE_TRAFFIC_DELAY]),
            route_line=self._route(values[ROLE_ROUTE_LINE]),
            odometer=reading.odometer,
            travelled=self._travelled(),
            last_trip=self.last_trip,
            latitude=position.latitude if located else None,
            longitude=position.longitude if located else None,
            position_at=position.reported_at if located else None,
            heading=number(heading),
            speed=reading.speed,
            battery=number(battery),
            **self._look(now),
        )
        self._save_later(now, bool(events))
        return view

    def _travelled(self) -> float | None:
        """The trail's length in the engine's miles."""
        length = self.trail.length_km
        if length is None:
            return None
        return DistanceConverter.convert(
            length, UnitOfLength.KILOMETERS, UnitOfLength.MILES
        )

    def _look(self, now: float) -> dict[str, str | None]:
        """How the car is drawn. Paint doesn't go stale, so restored values do."""
        options = self.config_entry.options
        car_type, paint, roof = (
            pick(self._samples(role), now, 0)
            for role in (ROLE_CAR_TYPE, ROLE_PAINT, ROLE_ROOF)
        )
        return {
            "model": options.get(CONF_CAR_MODEL)
            or car_model(car_type, self._device_model),
            "paint": options.get(CONF_CAR_COLOR) or paint,
            "roof": roof,
        }

    def _on_event(self, event: DriveEvent) -> None:
        if event.type == EVENT_DRIVE_STARTED:
            self.trail.clear()
        elif event.type == EVENT_DRIVE_ENDED:
            self.last_trip = dict(event.data)
        public = redact_event(event, self.hidden)
        for listener in self._event_listeners:
            listener(public)

    @callback
    def async_add_event_listener(self, listener: EventListener) -> CALLBACK_TYPE:
        """Hear drive events, already redacted."""
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    async def async_set_hidden(self, hidden: bool) -> None:
        """Hide or show the destination, saving before anything is published."""
        self.hidden = hidden
        await self._store.async_save(self._stored())
        self.async_set_updated_data(self._compute())

    def _stored(self) -> dict[str, Any]:
        return {
            "engine": self._engine.as_dict(),
            "pairing": self._pairing.as_dict(),
            "hide": "on" if self.hidden else "off",
            "last_trip": self.last_trip,
            "trail": self.trail.points,
        }

    def _save_later(self, now: float, soon: bool) -> None:
        """Save at a steady pace, because a delayed save restarts on every call."""
        if soon or now - self._saved_at >= SAVE_EVERY_SECONDS:
            self._saved_at = now
            self._store.async_delay_save(self._stored, 1)

    async def async_save(self) -> None:
        """Write everything now, for an unload."""
        await self._store.async_save(self._stored())

    @callback
    def async_close_subscribers(self) -> None:
        """Tell open websockets this car has gone."""
        for close in list(self.closers):
            close()


