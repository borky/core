"""The tests for the Prometheus exporter."""
from dataclasses import dataclass
import datetime
from http import HTTPStatus
from unittest import mock

import prometheus_client
import pytest

from homeassistant.components import (
    binary_sensor,
    climate,
    counter,
    device_tracker,
    humidifier,
    input_boolean,
    input_number,
    light,
    lock,
    person,
    prometheus,
    sensor,
    switch,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
)
from homeassistant.components.humidifier import ATTR_AVAILABLE_MODES
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONTENT_TYPE_TEXT_PLAIN,
    DEGREE,
    ENERGY_KILO_WATT_HOUR,
    EVENT_STATE_CHANGED,
    PERCENTAGE,
    STATE_HOME,
    STATE_LOCKED,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_UNLOCKED,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import split_entity_id
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

PROMETHEUS_PATH = "homeassistant.components.prometheus"


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


@pytest.fixture(name="client")
async def setup_prometheus_client(hass, hass_client, namespace):
    """Initialize an hass_client with Prometheus component."""
    # Reset registry
    prometheus_client.REGISTRY = prometheus_client.CollectorRegistry(auto_describe=True)
    prometheus_client.ProcessCollector(registry=prometheus_client.REGISTRY)
    prometheus_client.PlatformCollector(registry=prometheus_client.REGISTRY)
    prometheus_client.GCCollector(registry=prometheus_client.REGISTRY)

    config = {}
    if namespace is not None:
        config[prometheus.CONF_PROM_NAMESPACE] = namespace
    assert await async_setup_component(
        hass, prometheus.DOMAIN, {prometheus.DOMAIN: config}
    )
    await hass.async_block_till_done()

    return await hass_client()


async def generate_latest_metrics(client):
    """Generate the latest metrics and transform the body."""
    resp = await client.get(prometheus.API_ENDPOINT)
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == CONTENT_TYPE_TEXT_PLAIN
    body = await resp.text()
    body = body.split("\n")

    assert len(body) > 3

    return body


@pytest.mark.parametrize("namespace", [""])
async def test_view_empty_namespace(client, sensor_entities):
    """Test prometheus metrics view."""
    body = await generate_latest_metrics(client)

    assert "# HELP python_info Python platform information" in body
    assert (
        "# HELP python_gc_objects_collected_total "
        "Objects collected during gc" in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 1.0' in body
    )

    assert (
        'last_updated_time_seconds{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 86400.0' in body
    )


@pytest.mark.parametrize("namespace", [None])
async def test_view_default_namespace(client, sensor_entities):
    """Test prometheus metrics view."""
    body = await generate_latest_metrics(client)

    assert "# HELP python_info Python platform information" in body
    assert (
        "# HELP python_gc_objects_collected_total "
        "Objects collected during gc" in body
    )

    assert (
        'homeassistant_sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_sensor_unit(client, sensor_entities):
    """Test prometheus metrics for sensors with a unit."""
    body = await generate_latest_metrics(client)

    assert (
        'sensor_unit_kwh{domain="sensor",'
        'entity="sensor.television_energy",'
        'friendly_name="Television Energy"} 74.0' in body
    )

    assert (
        'sensor_unit_sek_per_kwh{domain="sensor",'
        'entity="sensor.electricity_price",'
        'friendly_name="Electricity price"} 0.123' in body
    )

    assert (
        'sensor_unit_u0xb0{domain="sensor",'
        'entity="sensor.wind_direction",'
        'friendly_name="Wind Direction"} 25.0' in body
    )

    assert (
        'sensor_unit_u0xb5g_per_mu0xb3{domain="sensor",'
        'entity="sensor.sps30_pm_1um_weight_concentration",'
        'friendly_name="SPS30 PM <1µm Weight concentration"} 3.7069' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_sensor_without_unit(client, sensor_entities):
    """Test prometheus metrics for sensors without a unit."""
    body = await generate_latest_metrics(client)

    assert (
        'sensor_state{domain="sensor",'
        'entity="sensor.trend_gradient",'
        'friendly_name="Trend Gradient"} 0.002' in body
    )

    assert (
        'sensor_state{domain="sensor",'
        'entity="sensor.text",'
        'friendly_name="Text"} 0' not in body
    )

    assert (
        'sensor_unit_text{domain="sensor",'
        'entity="sensor.text_unit",'
        'friendly_name="Text Unit"} 0' not in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_sensor_device_class(client, sensor_entities):
    """Test prometheus metrics for sensor with a device_class."""
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.fahrenheit",'
        'friendly_name="Fahrenheit"} 10.0' in body
    )

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'sensor_power_kwh{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 14.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_input_number(client, input_number_entities):
    """Test prometheus metrics for input_number."""
    body = await generate_latest_metrics(client)

    assert (
        'input_number_state{domain="input_number",'
        'entity="input_number.threshold",'
        'friendly_name="Threshold"} 5.2' in body
    )

    assert (
        'input_number_state{domain="input_number",'
        'entity="input_number.brightness",'
        'friendly_name="None"} 60.0' in body
    )

    assert (
        'input_number_state_celsius{domain="input_number",'
        'entity="input_number.target_temperature",'
        'friendly_name="Target temperature"} 22.7' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_battery(client, sensor_entities):
    """Test prometheus metrics for battery."""
    body = await generate_latest_metrics(client)

    assert (
        'battery_level_percent{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 12.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_climate(client, climate_entities):
    """Test prometheus metrics for climate entities."""
    body = await generate_latest_metrics(client)

    assert (
        'climate_current_temperature_celsius{domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 25.0' in body
    )

    assert (
        'climate_target_temperature_celsius{domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 20.0' in body
    )

    assert (
        'climate_target_temperature_low_celsius{domain="climate",'
        'entity="climate.ecobee",'
        'friendly_name="Ecobee"} 21.0' in body
    )

    assert (
        'climate_target_temperature_high_celsius{domain="climate",'
        'entity="climate.ecobee",'
        'friendly_name="Ecobee"} 24.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_humidifier(client, humidifier_entities):
    """Test prometheus metrics for humidifier entities."""
    body = await generate_latest_metrics(client)

    assert (
        'humidifier_target_humidity_percent{domain="humidifier",'
        'entity="humidifier.humidifier",'
        'friendly_name="Humidifier"} 68.0' in body
    )

    assert (
        'humidifier_state{domain="humidifier",'
        'entity="humidifier.dehumidifier",'
        'friendly_name="Dehumidifier"} 1.0' in body
    )

    assert (
        'humidifier_mode{domain="humidifier",'
        'entity="humidifier.hygrostat",'
        'friendly_name="Hygrostat",'
        'mode="home"} 1.0' in body
    )
    assert (
        'humidifier_mode{domain="humidifier",'
        'entity="humidifier.hygrostat",'
        'friendly_name="Hygrostat",'
        'mode="eco"} 0.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_attributes(client, switch_entities):
    """Test prometheus metrics for entity attributes."""
    body = await generate_latest_metrics(client)

    assert (
        'switch_state{domain="switch",'
        'entity="switch.boolean",'
        'friendly_name="Boolean"} 1.0' in body
    )

    assert (
        'switch_attr_boolean{domain="switch",'
        'entity="switch.boolean",'
        'friendly_name="Boolean"} 1.0' in body
    )

    assert (
        'switch_state{domain="switch",'
        'entity="switch.number",'
        'friendly_name="Number"} 0.0' in body
    )

    assert (
        'switch_attr_number{domain="switch",'
        'entity="switch.number",'
        'friendly_name="Number"} 10.2' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_binary_sensor(client, binary_sensor_entities):
    """Test prometheus metrics for binary_sensor."""
    body = await generate_latest_metrics(client)

    assert (
        'binary_sensor_state{domain="binary_sensor",'
        'entity="binary_sensor.door",'
        'friendly_name="Door"} 1.0' in body
    )

    assert (
        'binary_sensor_state{domain="binary_sensor",'
        'entity="binary_sensor.window",'
        'friendly_name="Window"} 0.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_input_boolean(client, input_boolean_entities):
    """Test prometheus metrics for input_boolean."""
    body = await generate_latest_metrics(client)

    assert (
        'input_boolean_state{domain="input_boolean",'
        'entity="input_boolean.test",'
        'friendly_name="Test"} 1.0' in body
    )

    assert (
        'input_boolean_state{domain="input_boolean",'
        'entity="input_boolean.helper",'
        'friendly_name="Helper"} 0.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_light(client, light_entities):
    """Test prometheus metrics for lights."""
    body = await generate_latest_metrics(client)

    assert (
        'light_brightness_percent{domain="light",'
        'entity="light.desk",'
        'friendly_name="Desk"} 100.0' in body
    )

    assert (
        'light_brightness_percent{domain="light",'
        'entity="light.wall",'
        'friendly_name="Wall"} 0.0' in body
    )

    assert (
        'light_brightness_percent{domain="light",'
        'entity="light.tv",'
        'friendly_name="TV"} 100.0' in body
    )

    assert (
        'light_brightness_percent{domain="light",'
        'entity="light.pc",'
        'friendly_name="PC"} 70.58823529411765' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_lock(client, lock_entities):
    """Test prometheus metrics for lock."""
    body = await generate_latest_metrics(client)

    assert (
        'lock_state{domain="lock",'
        'entity="lock.front_door",'
        'friendly_name="Front Door"} 1.0' in body
    )

    assert (
        'lock_state{domain="lock",'
        'entity="lock.kitchen_door",'
        'friendly_name="Kitchen Door"} 0.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_counter(client, counter_entities):
    """Test prometheus metrics for counter."""
    body = await generate_latest_metrics(client)

    assert (
        'counter_value{domain="counter",'
        'entity="counter.counter",'
        'friendly_name="None"} 2.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_renaming_entity_name(
    hass, registry, client, sensor_entities, climate_entities
):
    """Test renaming entity name."""
    data = {**sensor_entities, **climate_entities}
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )

    assert (
        'climate_action{action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 1.0' in body
    )

    assert (
        'climate_action{action="cooling",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 0.0' in body
    )

    assert "sensor.outside_temperature" in registry.entities
    assert "climate.heatpump" in registry.entities
    registry.async_update_entity(
        entity_id=data["sensor_1"].entity_id,
        name="Outside Temperature Renamed",
    )
    set_state_with_entry(
        hass,
        data["sensor_1"],
        15.6,
        {ATTR_FRIENDLY_NAME: "Outside Temperature Renamed"},
    )
    registry.async_update_entity(
        entity_id=data["climate_1"].entity_id,
        name="HeatPump Renamed",
    )
    data["climate_1_attributes"] = {
        **data["climate_1_attributes"],
        ATTR_FRIENDLY_NAME: "HeatPump Renamed",
    }
    set_state_with_entry(
        hass, data["climate_1"], CURRENT_HVAC_HEAT, data["climate_1_attributes"]
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Check if new metrics created
    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature Renamed"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature Renamed"} 1.0' in body
    )

    assert (
        'climate_action{action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump Renamed"} 1.0' in body
    )

    assert (
        'climate_action{action="cooling",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump Renamed"} 0.0' in body
    )

    # Keep other sensors
    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_renaming_entity_id(
    hass, registry, client, sensor_entities, climate_entities
):
    """Test renaming entity id."""
    data = {**sensor_entities, **climate_entities}
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )

    assert "sensor.outside_temperature" in registry.entities
    assert "climate.heatpump" in registry.entities
    registry.async_update_entity(
        entity_id="sensor.outside_temperature",
        new_entity_id="sensor.outside_temperature_renamed",
    )
    set_state_with_entry(
        hass, data["sensor_1"], 15.6, None, "sensor.outside_temperature_renamed"
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line

    # Check if new metrics created
    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature_renamed",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature_renamed",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    # Keep other sensors
    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_deleting_entity(
    hass, registry, client, sensor_entities, climate_entities
):
    """Test deleting a entity."""
    data = {**sensor_entities, **climate_entities}
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )

    assert (
        'climate_action{action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 1.0' in body
    )

    assert (
        'climate_action{action="cooling",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 0.0' in body
    )

    assert "sensor.outside_temperature" in registry.entities
    assert "climate.heatpump" in registry.entities
    registry.async_remove(data["sensor_1"].entity_id)
    registry.async_remove(data["climate_1"].entity_id)

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'entity="climate.heatpump"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Keep other sensors
    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )


@pytest.mark.parametrize("namespace", [""])
async def test_disabling_entity(
    hass, registry, client, sensor_entities, climate_entities
):
    """Test disabling a entity."""
    data = {**sensor_entities, **climate_entities}

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'state_change_total{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    assert any(
        'state_change_created{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"}' in metric
        for metric in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )

    assert (
        'climate_action{action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 1.0' in body
    )

    assert (
        'climate_action{action="cooling",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 0.0' in body
    )

    assert "sensor.outside_temperature" in registry.entities
    assert "climate.heatpump" in registry.entities
    registry.async_update_entity(
        entity_id=data["sensor_1"].entity_id,
        disabled_by=entity_registry.RegistryEntryDisabler.USER,
    )
    registry.async_update_entity(
        entity_id="climate.heatpump",
        disabled_by=entity_registry.RegistryEntryDisabler.USER,
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'entity="climate.heatpump"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Keep other sensors
    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )


@pytest.fixture(name="registry")
def entity_registry_fixture(hass):
    """Provide entity registry."""
    return entity_registry.async_get(hass)


@pytest.fixture(name="sensor_entities")
async def sensor_fixture(hass, registry):
    """Simulate sensor entities."""
    data = {}
    sensor_1 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_1",
        unit_of_measurement=TEMP_CELSIUS,
        original_device_class=SensorDeviceClass.TEMPERATURE,
        suggested_object_id="outside_temperature",
        original_name="Outside Temperature",
    )
    sensor_1_attributes = {ATTR_BATTERY_LEVEL: 12}
    set_state_with_entry(hass, sensor_1, 15.6, sensor_1_attributes)
    data["sensor_1"] = sensor_1
    data["sensor_1_attributes"] = sensor_1_attributes

    sensor_2 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_2",
        unit_of_measurement=PERCENTAGE,
        original_device_class=SensorDeviceClass.HUMIDITY,
        suggested_object_id="outside_humidity",
        original_name="Outside Humidity",
    )
    set_state_with_entry(hass, sensor_2, 54.0)
    data["sensor_2"] = sensor_2

    sensor_3 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_3",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        original_device_class=SensorDeviceClass.POWER,
        suggested_object_id="radio_energy",
        original_name="Radio Energy",
    )
    with mock.patch(
        "homeassistant.util.dt.utcnow",
        return_value=datetime.datetime(1970, 1, 2, tzinfo=dt_util.UTC),
    ):
        set_state_with_entry(hass, sensor_3, 14)
    data["sensor_3"] = sensor_3

    sensor_4 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_4",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        suggested_object_id="television_energy",
        original_name="Television Energy",
    )
    set_state_with_entry(hass, sensor_4, 74)
    data["sensor_4"] = sensor_4

    sensor_5 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_5",
        unit_of_measurement=f"SEK/{ENERGY_KILO_WATT_HOUR}",
        suggested_object_id="electricity_price",
        original_name="Electricity price",
    )
    set_state_with_entry(hass, sensor_5, 0.123)
    data["sensor_5"] = sensor_5

    sensor_6 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_6",
        unit_of_measurement=DEGREE,
        suggested_object_id="wind_direction",
        original_name="Wind Direction",
    )
    set_state_with_entry(hass, sensor_6, 25)
    data["sensor_6"] = sensor_6

    sensor_7 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_7",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_object_id="sps30_pm_1um_weight_concentration",
        original_name="SPS30 PM <1µm Weight concentration",
    )
    set_state_with_entry(hass, sensor_7, 3.7069)
    data["sensor_7"] = sensor_7

    sensor_8 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_8",
        suggested_object_id="trend_gradient",
        original_name="Trend Gradient",
    )
    set_state_with_entry(hass, sensor_8, 0.002)
    data["sensor_8"] = sensor_8

    sensor_9 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_9",
        suggested_object_id="text",
        original_name="Text",
    )
    set_state_with_entry(hass, sensor_9, "should_not_work")
    data["sensor_9"] = sensor_9

    sensor_10 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_10",
        unit_of_measurement="Text",
        suggested_object_id="text_unit",
        original_name="Text Unit",
    )
    set_state_with_entry(hass, sensor_10, "should_not_work")
    data["sensor_10"] = sensor_10

    sensor_11 = registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_11",
        unit_of_measurement=TEMP_FAHRENHEIT,
        original_device_class=SensorDeviceClass.TEMPERATURE,
        suggested_object_id="fahrenheit",
        original_name="Fahrenheit",
    )
    set_state_with_entry(hass, sensor_11, 50)
    data["sensor_11"] = sensor_11

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="climate_entities")
async def climate_fixture(hass, registry):
    """Simulate climate entities."""
    data = {}
    climate_1 = registry.async_get_or_create(
        domain=climate.DOMAIN,
        platform="test",
        unique_id="climate_1",
        unit_of_measurement=TEMP_CELSIUS,
        suggested_object_id="heatpump",
        original_name="HeatPump",
    )
    climate_1_attributes = {
        ATTR_TEMPERATURE: 20,
        ATTR_CURRENT_TEMPERATURE: 25,
        ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
    }
    set_state_with_entry(hass, climate_1, CURRENT_HVAC_HEAT, climate_1_attributes)
    data["climate_1"] = climate_1
    data["climate_1_attributes"] = climate_1_attributes

    climate_2 = registry.async_get_or_create(
        domain=climate.DOMAIN,
        platform="test",
        unique_id="climate_2",
        unit_of_measurement=TEMP_CELSIUS,
        suggested_object_id="ecobee",
        original_name="Ecobee",
    )
    climate_2_attributes = {
        ATTR_TEMPERATURE: 21,
        ATTR_CURRENT_TEMPERATURE: 22,
        ATTR_TARGET_TEMP_LOW: 21,
        ATTR_TARGET_TEMP_HIGH: 24,
        ATTR_HVAC_ACTION: CURRENT_HVAC_COOL,
    }
    set_state_with_entry(hass, climate_2, CURRENT_HVAC_HEAT, climate_2_attributes)
    data["climate_2"] = climate_2
    data["climate_2_attributes"] = climate_2_attributes

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="humidifier_entities")
async def humidifier_fixture(hass, registry):
    """Simulate humidifier entities."""
    data = {}
    humidifier_1 = registry.async_get_or_create(
        domain=humidifier.DOMAIN,
        platform="test",
        unique_id="humidifier_1",
        original_device_class=humidifier.HumidifierDeviceClass.HUMIDIFIER,
        suggested_object_id="humidifier",
        original_name="Humidifier",
    )
    humidifier_1_attributes = {
        ATTR_HUMIDITY: 68,
    }
    set_state_with_entry(hass, humidifier_1, STATE_ON, humidifier_1_attributes)
    data["humidifier_1"] = humidifier_1
    data["humidifier_1_attributes"] = humidifier_1_attributes

    humidifier_2 = registry.async_get_or_create(
        domain=humidifier.DOMAIN,
        platform="test",
        unique_id="humidifier_2",
        original_device_class=humidifier.HumidifierDeviceClass.DEHUMIDIFIER,
        suggested_object_id="dehumidifier",
        original_name="Dehumidifier",
    )
    humidifier_2_attributes = {
        ATTR_HUMIDITY: 54,
    }
    set_state_with_entry(hass, humidifier_2, STATE_ON, humidifier_2_attributes)
    data["humidifier_2"] = humidifier_2
    data["humidifier_2_attributes"] = humidifier_2_attributes

    humidifier_3 = registry.async_get_or_create(
        domain=humidifier.DOMAIN,
        platform="test",
        unique_id="humidifier_3",
        suggested_object_id="hygrostat",
        original_name="Hygrostat",
    )
    humidifier_3_attributes = {
        ATTR_HUMIDITY: 50,
        ATTR_MODE: "home",
        ATTR_AVAILABLE_MODES: ["home", "eco"],
    }
    set_state_with_entry(hass, humidifier_3, STATE_ON, humidifier_3_attributes)
    data["humidifier_3"] = humidifier_3
    data["humidifier_3_attributes"] = humidifier_3_attributes

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="lock_entities")
async def lock_fixture(hass, registry):
    """Simulate lock entities."""
    data = {}
    lock_1 = registry.async_get_or_create(
        domain=lock.DOMAIN,
        platform="test",
        unique_id="lock_1",
        suggested_object_id="front_door",
        original_name="Front Door",
    )
    set_state_with_entry(hass, lock_1, STATE_LOCKED)
    data["lock_1"] = lock_1

    lock_2 = registry.async_get_or_create(
        domain=lock.DOMAIN,
        platform="test",
        unique_id="lock_2",
        suggested_object_id="kitchen_door",
        original_name="Kitchen Door",
    )
    set_state_with_entry(hass, lock_2, STATE_UNLOCKED)
    data["lock_2"] = lock_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="input_number_entities")
async def input_number_fixture(hass, registry):
    """Simulate input_number entities."""
    data = {}
    input_number_1 = registry.async_get_or_create(
        domain=input_number.DOMAIN,
        platform="test",
        unique_id="input_number_1",
        suggested_object_id="threshold",
        original_name="Threshold",
    )
    set_state_with_entry(hass, input_number_1, 5.2)
    data["input_number_1"] = input_number_1

    input_number_2 = registry.async_get_or_create(
        domain=input_number.DOMAIN,
        platform="test",
        unique_id="input_number_2",
        suggested_object_id="brightness",
    )
    set_state_with_entry(hass, input_number_2, 60)
    data["input_number_2"] = input_number_2

    input_number_3 = registry.async_get_or_create(
        domain=input_number.DOMAIN,
        platform="test",
        unique_id="input_number_3",
        suggested_object_id="target_temperature",
        original_name="Target temperature",
        unit_of_measurement=TEMP_CELSIUS,
    )
    set_state_with_entry(hass, input_number_3, 22.7)
    data["input_number_3"] = input_number_3

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="input_boolean_entities")
async def input_boolean_fixture(hass, registry):
    """Simulate input_boolean entities."""
    data = {}
    input_boolean_1 = registry.async_get_or_create(
        domain=input_boolean.DOMAIN,
        platform="test",
        unique_id="input_boolean_1",
        suggested_object_id="test",
        original_name="Test",
    )
    set_state_with_entry(hass, input_boolean_1, STATE_ON)
    data["input_boolean_1"] = input_boolean_1

    input_boolean_2 = registry.async_get_or_create(
        domain=input_boolean.DOMAIN,
        platform="test",
        unique_id="input_boolean_2",
        suggested_object_id="helper",
        original_name="Helper",
    )
    set_state_with_entry(hass, input_boolean_2, STATE_OFF)
    data["input_boolean_2"] = input_boolean_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="binary_sensor_entities")
async def binary_sensor_fixture(hass, registry):
    """Simulate binary_sensor entities."""
    data = {}
    binary_sensor_1 = registry.async_get_or_create(
        domain=binary_sensor.DOMAIN,
        platform="test",
        unique_id="binary_sensor_1",
        suggested_object_id="door",
        original_name="Door",
    )
    set_state_with_entry(hass, binary_sensor_1, STATE_ON)
    data["binary_sensor_1"] = binary_sensor_1

    binary_sensor_2 = registry.async_get_or_create(
        domain=binary_sensor.DOMAIN,
        platform="test",
        unique_id="binary_sensor_2",
        suggested_object_id="window",
        original_name="Window",
    )
    set_state_with_entry(hass, binary_sensor_2, STATE_OFF)
    data["binary_sensor_2"] = binary_sensor_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="light_entities")
async def light_fixture(hass, registry):
    """Simulate light entities."""
    data = {}
    light_1 = registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_1",
        suggested_object_id="desk",
        original_name="Desk",
    )
    set_state_with_entry(hass, light_1, STATE_ON)
    data["light_1"] = light_1

    light_2 = registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_2",
        suggested_object_id="wall",
        original_name="Wall",
    )
    set_state_with_entry(hass, light_2, STATE_OFF)
    data["light_2"] = light_2

    light_3 = registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_3",
        suggested_object_id="tv",
        original_name="TV",
    )
    light_3_attributes = {light.ATTR_BRIGHTNESS: 255}
    set_state_with_entry(hass, light_3, STATE_ON, light_3_attributes)
    data["light_3"] = light_3
    data["light_3_attributes"] = light_3_attributes

    light_4 = registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_4",
        suggested_object_id="pc",
        original_name="PC",
    )
    light_4_attributes = {light.ATTR_BRIGHTNESS: 180}
    set_state_with_entry(hass, light_4, STATE_ON, light_4_attributes)
    data["light_4"] = light_4
    data["light_4_attributes"] = light_4_attributes

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="switch_entities")
async def switch_fixture(hass, registry):
    """Simulate switch entities."""
    data = {}
    switch_1 = registry.async_get_or_create(
        domain=switch.DOMAIN,
        platform="test",
        unique_id="switch_1",
        suggested_object_id="boolean",
        original_name="Boolean",
    )
    switch_1_attributes = {"boolean": True}
    set_state_with_entry(hass, switch_1, STATE_ON, switch_1_attributes)
    data["switch_1"] = switch_1
    data["switch_1_attributes"] = switch_1_attributes

    switch_2 = registry.async_get_or_create(
        domain=switch.DOMAIN,
        platform="test",
        unique_id="switch_2",
        suggested_object_id="number",
        original_name="Number",
    )
    switch_2_attributes = {"Number": 10.2}
    set_state_with_entry(hass, switch_2, STATE_OFF, switch_2_attributes)
    data["switch_2"] = switch_2
    data["switch_2_attributes"] = switch_2_attributes

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="person_entities")
async def person_fixture(hass, registry):
    """Simulate person entities."""
    data = {}
    person_1 = registry.async_get_or_create(
        domain=person.DOMAIN,
        platform="test",
        unique_id="person_1",
        suggested_object_id="bob",
        original_name="Bob",
    )
    set_state_with_entry(hass, person_1, STATE_HOME)
    data["person_1"] = person_1

    person_2 = registry.async_get_or_create(
        domain=person.DOMAIN,
        platform="test",
        unique_id="person_2",
        suggested_object_id="alice",
        original_name="Alice",
    )
    set_state_with_entry(hass, person_2, STATE_NOT_HOME)
    data["person_2"] = person_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="device_tracker_entities")
async def device_tracker_fixture(hass, registry):
    """Simulate device_tracker entities."""
    data = {}
    device_tracker_1 = registry.async_get_or_create(
        domain=device_tracker.DOMAIN,
        platform="test",
        unique_id="device_tracker_1",
        suggested_object_id="phone",
        original_name="Phone",
    )
    set_state_with_entry(hass, device_tracker_1, STATE_HOME)
    data["device_tracker_1"] = device_tracker_1

    device_tracker_2 = registry.async_get_or_create(
        domain=device_tracker.DOMAIN,
        platform="test",
        unique_id="device_tracker_2",
        suggested_object_id="watch",
        original_name="Watch",
    )
    set_state_with_entry(hass, device_tracker_2, STATE_NOT_HOME)
    data["device_tracker_2"] = device_tracker_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="counter_entities")
async def counter_fixture(hass, registry):
    """Simulate counter entities."""
    data = {}
    counter_1 = registry.async_get_or_create(
        domain=counter.DOMAIN,
        platform="test",
        unique_id="counter_1",
        suggested_object_id="counter",
    )
    set_state_with_entry(hass, counter_1, 2)
    data["counter_1"] = counter_1

    await hass.async_block_till_done()
    return data


def set_state_with_entry(
    hass,
    entry: entity_registry.RegistryEntry,
    state,
    additional_attributes=None,
    new_entity_id=None,
):
    """Set the state of an entity with an Entity Registry entry."""
    attributes = {}

    if entry.original_name:
        attributes[ATTR_FRIENDLY_NAME] = entry.original_name
    if entry.unit_of_measurement:
        attributes[ATTR_UNIT_OF_MEASUREMENT] = entry.unit_of_measurement
    if entry.original_device_class:
        attributes[ATTR_DEVICE_CLASS] = entry.original_device_class

    if additional_attributes:
        attributes = {**attributes, **additional_attributes}

    hass.states.async_set(
        entity_id=new_entity_id if new_entity_id else entry.entity_id,
        new_state=state,
        attributes=attributes,
    )


@pytest.fixture(name="mock_client")
def mock_client_fixture():
    """Mock the prometheus client."""
    with mock.patch(f"{PROMETHEUS_PATH}.prometheus_client") as client:
        counter_client = mock.MagicMock()
        client.Counter = mock.MagicMock(return_value=counter_client)
        setattr(counter_client, "labels", mock.MagicMock(return_value=mock.MagicMock()))
        yield counter_client


@pytest.fixture
def mock_bus(hass):
    """Mock the event bus listener."""
    hass.bus.listen = mock.MagicMock()


@pytest.mark.usefixtures("mock_bus")
async def test_minimal_config(hass, mock_client):
    """Test the minimal config and defaults of component."""
    config = {prometheus.DOMAIN: {}}
    assert await async_setup_component(hass, prometheus.DOMAIN, config)
    await hass.async_block_till_done()
    assert hass.bus.listen.called
    assert hass.bus.listen.call_args_list[0][0][0] == EVENT_STATE_CHANGED


@pytest.mark.usefixtures("mock_bus")
async def test_full_config(hass, mock_client):
    """Test the full config of component."""
    config = {
        prometheus.DOMAIN: {
            "namespace": "ns",
            "default_metric": "m",
            "override_metric": "m",
            "component_config": {"fake.test": {"override_metric": "km"}},
            "component_config_glob": {"fake.time_*": {"override_metric": "h"}},
            "component_config_domain": {"climate": {"override_metric": "°C"}},
            "filter": {
                "include_domains": ["climate"],
                "include_entity_globs": ["fake.time_*"],
                "include_entities": ["fake.test"],
                "exclude_domains": ["script"],
                "exclude_entity_globs": ["climate.excluded_*"],
                "exclude_entities": ["fake.time_excluded"],
            },
        }
    }
    assert await async_setup_component(hass, prometheus.DOMAIN, config)
    await hass.async_block_till_done()
    assert hass.bus.listen.called
    assert hass.bus.listen.call_args_list[0][0][0] == EVENT_STATE_CHANGED


def make_event(entity_id):
    """Make a mock event for test."""
    domain = split_entity_id(entity_id)[0]
    state = mock.MagicMock(
        state="not blank",
        domain=domain,
        entity_id=entity_id,
        object_id="entity",
        attributes={},
    )
    return mock.MagicMock(data={"new_state": state}, time_fired=12345)


async def _setup(hass, filter_config):
    """Shared set up for filtering tests."""
    config = {prometheus.DOMAIN: {"filter": filter_config}}
    assert await async_setup_component(hass, prometheus.DOMAIN, config)
    await hass.async_block_till_done()
    return hass.bus.listen.call_args_list[0][0][1]


@pytest.mark.usefixtures("mock_bus")
async def test_allowlist(hass, mock_client):
    """Test an allowlist only config."""
    handler_method = await _setup(
        hass,
        {
            "include_domains": ["fake"],
            "include_entity_globs": ["test.included_*"],
            "include_entities": ["not_real.included"],
        },
    )

    tests = [
        FilterTest("climate.excluded", False),
        FilterTest("fake.included", True),
        FilterTest("test.excluded_test", False),
        FilterTest("test.included_test", True),
        FilterTest("not_real.included", True),
        FilterTest("not_real.excluded", False),
    ]

    for test in tests:
        event = make_event(test.id)
        handler_method(event)

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()


@pytest.mark.usefixtures("mock_bus")
async def test_denylist(hass, mock_client):
    """Test a denylist only config."""
    handler_method = await _setup(
        hass,
        {
            "exclude_domains": ["fake"],
            "exclude_entity_globs": ["test.excluded_*"],
            "exclude_entities": ["not_real.excluded"],
        },
    )

    tests = [
        FilterTest("fake.excluded", False),
        FilterTest("light.included", True),
        FilterTest("test.excluded_test", False),
        FilterTest("test.included_test", True),
        FilterTest("not_real.included", True),
        FilterTest("not_real.excluded", False),
    ]

    for test in tests:
        event = make_event(test.id)
        handler_method(event)

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()


@pytest.mark.usefixtures("mock_bus")
async def test_filtered_denylist(hass, mock_client):
    """Test a denylist config with a filtering allowlist."""
    handler_method = await _setup(
        hass,
        {
            "include_entities": ["fake.included", "test.excluded_test"],
            "exclude_domains": ["fake"],
            "exclude_entity_globs": ["*.excluded_*"],
            "exclude_entities": ["not_real.excluded"],
        },
    )

    tests = [
        FilterTest("fake.excluded", False),
        FilterTest("fake.included", True),
        FilterTest("alt_fake.excluded_test", False),
        FilterTest("test.excluded_test", True),
        FilterTest("not_real.excluded", False),
        FilterTest("not_real.included", True),
    ]

    for test in tests:
        event = make_event(test.id)
        handler_method(event)

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()
