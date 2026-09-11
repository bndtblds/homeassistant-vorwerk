"""Tests for the Vorwerk battery sensor."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE

from custom_components.vorwerk import VorwerkRobotState
from custom_components.vorwerk.sensor import VorwerkBatterySensor


def test_battery_sensor(
    coordinator: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test battery sensor metadata and value."""
    robot_state.robot_state = {"state": 1, "details": {"charge": "73"}}
    entity = VorwerkBatterySensor(coordinator)

    assert entity.unique_id == "VR300-1234_battery"
    assert entity.device_class is SensorDeviceClass.BATTERY
    assert entity.native_unit_of_measurement == PERCENTAGE
    assert entity.state_class is SensorStateClass.MEASUREMENT
    assert entity.native_value == 73


def test_battery_sensor_missing_data(
    coordinator: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test missing and malformed battery data."""
    entity = VorwerkBatterySensor(coordinator)
    assert entity.native_value is None

    robot_state.robot_state = {"state": 1, "details": {"charge": "unknown"}}
    assert entity.native_value is None
