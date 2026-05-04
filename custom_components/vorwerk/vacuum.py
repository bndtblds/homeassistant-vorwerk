"""Vacuum platform for Vorwerk robots."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VorwerkConfigEntry
from .const import ROBOT_API_TIMEOUT, VORWERK_DOMAIN
from .entity import VorwerkEntity

_LOGGER = logging.getLogger(__name__)

ATTR_STATUS = "status"
PARALLEL_UPDATES = 1

ACTIVITY_TO_STATE = {
    VacuumActivity.DOCKED: "docked",
    VacuumActivity.IDLE: "idle",
    VacuumActivity.CLEANING: "cleaning",
    VacuumActivity.PAUSED: "paused",
    VacuumActivity.RETURNING: "returning",
    VacuumActivity.ERROR: "error",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VorwerkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vorwerk vacuum entities."""
    async_add_entities(
        [
            VorwerkVacuumEntity(robot_runtime.coordinator)
            for robot_runtime in entry.runtime_data.robots
        ]
    )


class VorwerkVacuumEntity(VorwerkEntity, StateVacuumEntity):
    """Representation of a Vorwerk vacuum cleaner."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:robot-vacuum"
    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.LOCATE
    )

    def __init__(self, coordinator) -> None:
        """Initialize the vacuum entity."""
        super().__init__(coordinator)
        self._attr_unique_id = self.robot.serial
        self._robot_boundaries: list[dict[str, Any]] = []
        self._boundaries_loaded = False

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current vacuum activity."""
        return self.robot_state.activity

    @property
    def state(self) -> str | None:
        """Return the legacy string state for the vacuum entity."""
        activity = self.activity
        if activity is None:
            return None
        return ACTIVITY_TO_STATE.get(activity)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if (status := self.robot_state.status) is None:
            return {}
        return {ATTR_STATUS: status}

    async def async_start(self) -> None:
        """Start or resume a cleaning run."""
        if self.activity == VacuumActivity.PAUSED:
            await self._async_call_robot_command(self.robot.resume_cleaning)
            return

        await self._async_call_robot_command(self.robot.start_cleaning)

    async def async_pause(self) -> None:
        """Pause the current cleaning run."""
        await self._async_call_robot_command(self.robot.pause_cleaning)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the current cleaning run."""
        await self._async_call_robot_command(self.robot.stop_cleaning)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send the robot back to the base."""
        if self.activity == VacuumActivity.CLEANING:
            await self._async_call_robot_command(
                self.robot.pause_cleaning,
                refresh=False,
            )

        await self._async_call_robot_command(self.robot.send_to_base)

    async def async_locate(self, **kwargs: Any) -> None:
        """Play the locate sound on the robot."""
        await self._async_call_robot_command(self.robot.locate)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Start a spot clean."""
        await self._async_call_robot_command(self.robot.start_spot_cleaning)

    async def async_custom_cleaning(
        self,
        mode: int,
        navigation: int,
        category: int,
        zone: str | None = None,
    ) -> None:
        """Start a custom cleaning run."""
        boundary_id = await self._async_resolve_boundary_id(zone)

        await self._async_call_robot_command(
            self.robot.start_cleaning,
            mode,
            navigation,
            category,
            boundary_id,
        )

    async def _async_resolve_boundary_id(self, zone: str | None) -> str | None:
        """Resolve a zone name to a boundary identifier."""
        if zone is None:
            return None

        await self._async_ensure_boundaries_loaded()

        normalized_zone = zone.casefold()
        for boundary in self._robot_boundaries:
            name = boundary.get("name")
            boundary_id = boundary.get("id")
            if not isinstance(name, str) or not isinstance(boundary_id, str):
                continue
            if normalized_zone in name.casefold():
                return boundary_id

        available_zones = sorted(
            boundary["name"]
            for boundary in self._robot_boundaries
            if isinstance(boundary.get("name"), str)
        )
        if available_zones:
            raise ServiceValidationError(
                translation_domain=VORWERK_DOMAIN,
                translation_key="zone_not_found",
                translation_placeholders={
                    "robot": self.robot.name,
                    "zone": zone,
                    "available_zones": ", ".join(available_zones),
                },
            )

        raise ServiceValidationError(
            translation_domain=VORWERK_DOMAIN,
            translation_key="no_map_boundaries",
            translation_placeholders={
                "robot": self.robot.name,
                "zone": zone,
            },
        )

    async def _async_ensure_boundaries_loaded(self) -> None:
        """Load zone boundaries from the robot once when needed."""
        if self._boundaries_loaded:
            return

        try:
            self._robot_boundaries = await asyncio.wait_for(
                self.hass.async_add_executor_job(self._load_map_boundaries),
                timeout=ROBOT_API_TIMEOUT,
            )
        except asyncio.TimeoutError as err:
            _LOGGER.warning("Timed out loading map boundaries for %s", self.robot.name)
            raise HomeAssistantError(
                translation_domain=VORWERK_DOMAIN,
                translation_key="load_map_boundaries_failed",
                translation_placeholders={"robot": self.robot.name},
            ) from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Unable to load map boundaries for %s: %s",
                self.robot.name,
                err,
            )
            raise HomeAssistantError(
                translation_domain=VORWERK_DOMAIN,
                translation_key="load_map_boundaries_failed",
                translation_placeholders={"robot": self.robot.name},
            ) from err

        self._boundaries_loaded = True

    def _load_map_boundaries(self) -> list[dict[str, Any]]:
        """Load zone boundaries from the blocking pybotvac API."""
        response = self.robot.get_map_boundaries().json()

        boundaries = response.get("data", {}).get("boundaries", [])
        if isinstance(boundaries, list):
            return [
                boundary for boundary in boundaries if isinstance(boundary, dict)
            ]
        return []
