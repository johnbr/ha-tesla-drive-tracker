"""The live feed for the card.

A fix arrives about once a second, and an entity attribute would write a recorder
row for each one, so this path never touches an entity. It is read-only, and it
sends only the redacted view, so it shows no more than entity state does.
"""
from __future__ import annotations

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import DriveCoordinator


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register the websocket commands."""
    websocket_api.async_register_command(hass, ws_cars)
    websocket_api.async_register_command(hass, ws_subscribe)


@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/cars"})
@callback
def ws_cars(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """The cars a card can show, by name, never by VIN."""
    connection.send_result(
        msg["id"],
        [
            {"entry_id": entry.entry_id, "name": entry.title}
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        ],
    )


def _changes(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in new.items() if value != old.get(key)}


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/subscribe",
        probatio.Required("entry_id"): str,
    }
)
@callback
def ws_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send one snapshot of a car, then what changes."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
    ):
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "No such car"
        )
        return

    coordinator: DriveCoordinator = entry.runtime_data
    sent = coordinator.data.as_wire()

    def send(message: dict[str, Any]) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], message))

    @callback
    def on_update() -> None:
        nonlocal sent
        current = coordinator.data.as_wire()
        changed = _changes(sent, current)
        if changed:
            sent = current
            send({"type": "delta", **changed})

    @callback
    def on_close() -> None:
        send({"type": "closed"})

    unsub_update = coordinator.async_add_listener(on_update)
    coordinator.closers.add(on_close)

    @callback
    def unsubscribe() -> None:
        unsub_update()
        coordinator.closers.discard(on_close)

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    send({"type": "snapshot", **sent, "trail": coordinator.trail.points})
