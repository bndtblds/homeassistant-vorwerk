"""Data update coordinator for Vorwerk robots."""
from __future__ import annotations

import asyncio
import logging

from pybotvac.exceptions import NeatoException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MIN_TIME_BETWEEN_UPDATES, ROBOT_API_TIMEOUT

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
        self._update_future: asyncio.Future[None] | None = None

    async def _async_update_data(self) -> "VorwerkRobotState":
        """Fetch the latest robot data."""
        if self._update_future is not None and not self._update_future.done():
            raise UpdateFailed(
                f"Previous update for Vorwerk robot {self.robot_state.robot.name} "
                "is still running"
            )

        self._update_future = self.hass.async_add_executor_job(self.robot_state.update)
        self._update_future.add_done_callback(self._async_clear_update_future)

        try:
            await asyncio.wait_for(
                asyncio.shield(self._update_future),
                timeout=ROBOT_API_TIMEOUT,
            )
        except asyncio.TimeoutError as err:
            raise UpdateFailed(
                f"Timed out updating Vorwerk robot {self.robot_state.robot.name}"
            ) from err
        except NeatoException as err:
            raise UpdateFailed(
                f"Error communicating with Vorwerk robot {self.robot_state.robot.name}: {err}"
            ) from err
        return self.robot_state

    def _async_clear_update_future(self, future: asyncio.Future[None]) -> None:
        """Clear finished update jobs and consume delayed executor exceptions."""
        if self._update_future is future:
            self._update_future = None

        if future.cancelled():
            return

        future.exception()
