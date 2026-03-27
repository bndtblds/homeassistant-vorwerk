"""Sensor platform for Vorwerk robots."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VorwerkConfigEntry
from .entity import VorwerkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VorwerkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vorwerk sensors."""
    async_add_entities(
        [
            VorwerkBatterySensor(robot_runtime.coordinator)
            for robot_runtime in entry.runtime_data.robots
        ]
    )


class VorwerkBatterySensor(VorwerkEntity, SensorEntity):
    """Battery level sensor for a Vorwerk robot."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_has_entity_name = True
    _attr_translation_key = "battery"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.robot.serial}_battery"

    @property
    def native_value(self) -> int | None:
        """Return battery level as a percentage."""
        return self.robot_state.battery_level
