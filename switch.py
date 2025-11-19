"""Support for Vorwerk Connected Vacuums switches."""
from __future__ import annotations

import logging
from typing import Any

from pybotvac.exceptions import NeatoRobotException
from pybotvac.robot import Robot

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import VorwerkState
from .const import (
    VORWERK_DOMAIN,
    VORWERK_ROBOT_API,
    VORWERK_ROBOT_COORDINATOR,
    VORWERK_ROBOTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Vorwerk switches from a config entry."""
    _LOGGER.debug("Adding switches for vorwerk (%s)", entry.title)

    dev: list[VorwerkScheduleSwitch] = [
        VorwerkScheduleSwitch(
            robot[VORWERK_ROBOT_API], robot[VORWERK_ROBOT_COORDINATOR]
        )
        for robot in hass.data[VORWERK_DOMAIN][entry.entry_id][VORWERK_ROBOTS]
    ]

    if not dev:
        return

    async_add_entities(dev, True)


class VorwerkScheduleSwitch(CoordinatorEntity, SwitchEntity):
    """Vorwerk Schedule Switch."""

    def __init__(
        self, robot_state: VorwerkState, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize the Vorwerk Schedule switch."""
        super().__init__(coordinator)
        self.robot: Robot = robot_state.robot
        self._state: VorwerkState = robot_state
        self._robot_name = f"{self.robot.name} Schedule"
        self._robot_serial = self.robot.serial

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._robot_name

    @property
    def available(self) -> bool:
        """Return if the switch is available."""
        return self._state.available

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this switch."""
        return self._robot_serial

    @property
    def is_on(self) -> bool:
        """Return true if schedule is enabled."""
        return bool(self._state.schedule_enabled)

    @property
    def device_info(self):
        """Return device information for this switch."""
        return self._state.device_info

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on (enable schedule)."""

        def turn_on():
            try:
                self.robot.enable_schedule()
            except NeatoRobotException as ex:
                _LOGGER.error(
                    "Vorwerk switch connection error '%s': %s", self.entity_id, ex
                )

        await self.hass.async_add_executor_job(turn_on)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off (disable schedule)."""

        def turn_off():
            try:
                self.robot.disable_schedule()
            except NeatoRobotException as ex:
                _LOGGER.error(
                    "Vorwerk switch connection error '%s': %s", self.entity_id, ex
                )

        await self.hass.async_add_executor_job(turn_off)
        await self.coordinator.async_request_refresh()
