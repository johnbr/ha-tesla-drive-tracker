"""The card's live feed."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.tesla_drive_tracker.const import DOMAIN

from .conftest import Car

PLACE = {"latitude": 10.0, "longitude": 20.0}


async def subscribe(hass_ws_client, hass: HomeAssistant, entry_id: str):
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": f"{DOMAIN}/subscribe", "entry_id": entry_id}
    )
    result = await client.receive_json()
    return client, result


async def test_snapshot_then_only_what_changed(
    car: Car, hass: HomeAssistant, hass_ws_client
) -> None:
    await car.start()
    client, result = await subscribe(hass_ws_client, hass, car.entry.entry_id)
    assert result["success"]
    snapshot = (await client.receive_json())["event"]
    assert snapshot["type"] == "snapshot"
    assert snapshot["state"] == "parked"
    assert snapshot["trail"] == []

    await car.report("speed", "40")
    delta = (await client.receive_json())["event"]
    assert delta["type"] == "delta"
    assert delta["speed"] == 40.0
    assert delta["state"] == "driving"
    assert "battery" not in delta
    await car.stop()


async def test_hiding_clears_what_the_card_holds(
    car: Car, hass: HomeAssistant, hass_ws_client
) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await car.report("speed", "40")
    await car.report("destination", "Cafe", PLACE)
    client, _ = await subscribe(hass_ws_client, hass, car.entry.entry_id)
    snapshot = (await client.receive_json())["event"]
    assert snapshot["destination"] == "Cafe"

    await car.coordinator.async_set_hidden(True)
    delta = (await client.receive_json())["event"]
    assert delta["destination"] is None
    assert delta["destination_latitude"] is None
    assert delta["hidden"] is True
    await car.stop()


async def test_a_hidden_car_sends_no_destination_at_all(
    car: Car, hass: HomeAssistant, hass_ws_client
) -> None:
    await car.start()
    await car.report("speed", "40")
    await car.report("destination", "Cafe", PLACE)
    client, _ = await subscribe(hass_ws_client, hass, car.entry.entry_id)
    snapshot = (await client.receive_json())["event"]
    assert "Cafe" not in str(snapshot)
    assert snapshot["destination_latitude"] is None
    await car.stop()


async def test_an_unknown_car_is_refused(
    car: Car, hass: HomeAssistant, hass_ws_client
) -> None:
    await car.start()
    _, result = await subscribe(hass_ws_client, hass, "no_such_entry")
    assert not result["success"]
    assert result["error"]["code"] == "not_found"
    await car.stop()


async def test_another_integrations_entry_is_refused(
    car: Car, hass: HomeAssistant, hass_ws_client, source_entry
) -> None:
    await car.start()
    source_entry.mock_state(hass, ConfigEntryState.LOADED)
    _, result = await subscribe(hass_ws_client, hass, source_entry.entry_id)
    assert not result["success"]
    assert result["error"]["code"] == "not_found"
    await car.stop()


async def test_an_unloaded_car_says_so(
    car: Car, hass: HomeAssistant, hass_ws_client
) -> None:
    await car.start()
    client, _ = await subscribe(hass_ws_client, hass, car.entry.entry_id)
    await client.receive_json()
    await car.stop()
    assert (await client.receive_json())["event"] == {"type": "closed"}


async def test_cars_are_listed_without_their_vin(
    car: Car, hass: HomeAssistant, hass_ws_client
) -> None:
    await car.start()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/cars"})
    result = (await client.receive_json())["result"]
    assert result == [{"entry_id": car.entry.entry_id, "name": "Test Car"}]
    await car.stop()
