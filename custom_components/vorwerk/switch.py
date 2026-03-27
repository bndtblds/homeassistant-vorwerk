"""Switch platform for Vorwerk robots."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VorwerkConfigEntry
from .entity import VorwerkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VorwerkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vorwerk switches."""
    async_add_entities(
        [
            VorwerkScheduleSwitch(robot_runtime.coordinator)
            for robot_runtime in entry.runtime_data.robots
        ]
    )


class VorwerkScheduleSwitch(VorwerkEntity, SwitchEntity):
    """Expose the robot schedule as a switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-clock"
    _attr_translation_key = "schedule"

    def __init__(self, coordinator) -> None:
        """Initialize the schedule switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.robot.serial}_schedule"

    @property
    def is_on(self) -> bool:
        """Return whether the schedule is enabled."""
        return bool(self.robot_state.schedule_enabled)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the cleaning schedule."""
        await self._async_call_robot_command(self.robot.enable_schedule)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the cleaning schedule."""
        await self._async_call_robot_command(self.robot.disable_schedule)
