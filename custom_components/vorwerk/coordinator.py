"""Data update coordinator for Vorwerk robots."""
from __future__ import annotations

import logging

from pybotvac.exceptions import NeatoException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)


class VorwerkDataUpdateCoordinator(DataUpdateCoordinator["VorwerkRobotState"]):
    """Coordinate updates for a single Vorwerk robot."""

    def __init__(self, hass: HomeAssistant, robot_state: "VorwerkRobotState") -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"vorwerk_{robot_state.robot.serial}",
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.robot_state = robot_state

    async def _async_update_data(self) -> "VorwerkRobotState":
        """Fetch the latest robot data."""
        try:
            await self.hass.async_add_executor_job(self.robot_state.update)
        except NeatoException as err:
            raise UpdateFailed(
                f"Error communicating with Vorwerk robot {self.robot_state.robot.name}: {err}"
            ) from err
        return self.robot_state
