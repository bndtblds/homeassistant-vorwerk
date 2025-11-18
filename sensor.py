"""Support for Vorwerk sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    VORWERK_DOMAIN,
    VORWERK_ROBOTS,
    VORWERK_ROBOT_API,
    VORWERK_ROBOT_COORDINATOR,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Vorwerk sensors from a config entry."""
    data = hass.data[VORWERK_DOMAIN][entry.entry_id][VORWERK_ROBOTS]
    entities: list[SensorEntity] = []

    for robot in data:
        state = robot[VORWERK_ROBOT_API]
        coordinator = robot[VORWERK_ROBOT_COORDINATOR]
        entities.append(VorwerkBatterySensor(state, coordinator))

    async_add_entities(entities)


class VorwerkBatterySensor(CoordinatorEntity, SensorEntity):
    """Battery level for a Vorwerk robot."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:battery"

    def __init__(self, robot_state, coordinator) -> None:
        super().__init__(coordinator)
        self._state = robot_state
        # Anzeigename + IDs
        self._attr_name = f"{self._state.robot.name} Battery"
        self._attr_unique_id = f"{self._state.robot.serial}_battery"

    @property
    def native_value(self) -> int | None:
        """Return battery level as percentage."""
        level = self._state.battery_level
        try:
            return int(level) if level is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def available(self) -> bool:
        return bool(self._state.available)

    @property
    def device_info(self) -> dict[str, Any]:
        """Device info for robot."""
        return self._state.device_info
