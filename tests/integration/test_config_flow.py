"""Adding a car and setting its options."""
from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.tesla_drive_tracker.const import (
    CONF_ROLES,
    CONF_THRESHOLDS,
    CONF_VIN,
    DOMAIN,
)

from .conftest import VIN, Car


async def start_flow(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_no_cars_aborts(hass: HomeAssistant) -> None:
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_cars"


async def test_a_car_is_added(
    hass: HomeAssistant, car: Car, entry: MockConfigEntry
) -> None:
    await hass.config_entries.async_remove(entry.entry_id)
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_VIN: VIN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Car"
    assert result["data"] == {CONF_VIN: VIN}
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_a_car_already_added_is_not_offered(
    hass: HomeAssistant, car: Car
) -> None:
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_cars"


async def test_options_are_saved(hass: HomeAssistant, car: Car) -> None:
    await car.start()
    result = await hass.config_entries.options.async_init(car.entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_THRESHOLDS: ["5", "10"], "arrival": "sensor.waze"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_THRESHOLDS: [10.0, 5.0],
        CONF_ROLES: {"arrival": "sensor.waze"},
    }
    await hass.async_block_till_done()
    await car.stop()


async def test_a_bad_threshold_is_refused(hass: HomeAssistant, car: Car) -> None:
    await car.start()
    result = await hass.config_entries.options.async_init(car.entry.entry_id)
    for bad in (["soon"], ["0"], ["500"], []):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_THRESHOLDS: bad}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_THRESHOLDS: "invalid_thresholds"}
    await car.stop()
