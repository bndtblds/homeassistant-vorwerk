"""Data update coordinator for Vorwerk robots."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pybotvac.exceptions import NeatoException

from .const import MIN_TIME_BETWEEN_UPDATES, ROBOT_API_TIMEOUT
from .diagnostics import masked_robot_serial, robot_log_id

if TYPE_CHECKING:
    from . import VorwerkRobotState

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _ActiveUpdate:
    """Track an executor update across coordinator reloads."""

    future: asyncio.Future[None]
    started_at: float


_ACTIVE_UPDATES: dict[tuple[int, str], _ActiveUpdate] = {}


class VorwerkDataUpdateCoordinator(DataUpdateCoordinator["VorwerkRobotState"]):
    """Coordinate updates for a single Vorwerk robot."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        robot_state: VorwerkRobotState,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"vorwerk_{masked_robot_serial(robot_state.robot)}",
            update_interval=MIN_TIME_BETWEEN_UPDATES,
            config_entry=config_entry,
        )
        self.robot_state = robot_state
        self._update_future: asyncio.Future[None] | None = None
        self._update_key = (id(hass), robot_state.robot.serial)

    async def _async_update_data(self) -> VorwerkRobotState:
        """Fetch the latest robot data."""
        active_update = _ACTIVE_UPDATES.get(self._update_key)
        if active_update is not None and not active_update.future.done():
            elapsed = monotonic() - active_update.started_at
            _LOGGER.warning(
                "Previous update for Vorwerk robot %s is still running after "
                "%.1f seconds",
                robot_log_id(self.robot_state.robot),
                elapsed,
            )
            raise UpdateFailed(
                f"Previous update for Vorwerk robot {self.robot_state.robot.name} is "
                f"still running after {elapsed:.1f} seconds"
            )

        started_at = monotonic()
        update_future = self.hass.async_add_executor_job(self.robot_state.update)
        self._update_future = update_future
        _ACTIVE_UPDATES[self._update_key] = _ActiveUpdate(
            future=update_future,
            started_at=started_at,
        )
        update_future.add_done_callback(self._async_clear_update_future)

        try:
            done, _ = await asyncio.wait(
                (update_future,),
                timeout=ROBOT_API_TIMEOUT,
            )
            if not done:
                raise TimeoutError
            await update_future
        except TimeoutError as err:
            elapsed = monotonic() - started_at
            _LOGGER.warning(
                "Timed out updating Vorwerk robot %s after %.1f seconds; the "
                "blocking background call is still running",
                robot_log_id(self.robot_state.robot),
                elapsed,
            )
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

        active_update = _ACTIVE_UPDATES.get(self._update_key)
        if active_update is not None and active_update.future is future:
            elapsed = monotonic() - active_update.started_at
            del _ACTIVE_UPDATES[self._update_key]
            _LOGGER.debug(
                "Background update for Vorwerk robot %s finished after %.1f seconds",
                robot_log_id(self.robot_state.robot),
                elapsed,
            )

        if future.cancelled():
            return

        future.exception()
