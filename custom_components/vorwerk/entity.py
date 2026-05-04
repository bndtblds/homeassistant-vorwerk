"""Shared entity helpers for Vorwerk."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ROBOT_API_TIMEOUT, VORWERK_DOMAIN
from .coordinator import VorwerkDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class VorwerkEntity(CoordinatorEntity[VorwerkDataUpdateCoordinator]):
    """Base entity for Vorwerk platforms."""

    def __init__(self, coordinator: VorwerkDataUpdateCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.robot_state = coordinator.robot_state
        self.robot = self.robot_state.robot

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.robot_state.available

    @property
    def device_info(self):
        """Return device information for the robot."""
        return self.robot_state.device_info

    async def _async_call_robot_command(
        self,
        command: Callable[..., Any],
        *args: Any,
        refresh: bool = True,
    ) -> None:
        """Run a blocking robot command and optionally refresh the coordinator."""
        try:
            await asyncio.wait_for(
                self.hass.async_add_executor_job(command, *args),
                timeout=ROBOT_API_TIMEOUT,
            )
        except asyncio.TimeoutError as err:
            _LOGGER.error("Vorwerk command timed out for %s", self.robot.name)
            raise HomeAssistantError(
                translation_domain=VORWERK_DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"robot": self.robot.name},
            ) from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Vorwerk command failed for %s: %s", self.robot.name, err)
            raise HomeAssistantError(
                translation_domain=VORWERK_DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"robot": self.robot.name},
            ) from err
        if refresh:
            await self.coordinator.async_request_refresh()
