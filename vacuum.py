"""Support for Neato Connected Vacuums."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumEntityFeature,
    VacuumActivity,
)
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VorwerkState
from .const import (
    ATTR_CATEGORY,
    ATTR_NAVIGATION,
    ATTR_ZONE,
    VORWERK_DOMAIN,
    VORWERK_ROBOTS,
    VORWERK_ROBOT_API,
    VORWERK_ROBOT_COORDINATOR,
)

# Früher ATTR_STATUS aus vacuum, jetzt lokal:
ATTR_STATUS = "status"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Vorwerk vacuum from a config entry."""

    robots = hass.data[VORWERK_DOMAIN][entry.entry_id][VORWERK_ROBOTS]

    entities: list[StateVacuumEntity] = []

    for robot in robots:
        state: VorwerkState = robot[VORWERK_ROBOT_API]
        coordinator = robot[VORWERK_ROBOT_COORDINATOR]
        entities.append(VorwerkConnectedVacuum(state, coordinator))

    async_add_entities(entities, True)

    # Entity-Service wie in deiner alten Version
    platform = entity_platform.current_platform.get()
    assert platform is not None

    platform.async_register_entity_service(
        "custom_cleaning",
        {
            vol.Optional(ATTR_MODE, default=2): cv.positive_int,
            vol.Optional(ATTR_NAVIGATION, default=1): cv.positive_int,
            vol.Optional(ATTR_CATEGORY, default=4): cv.positive_int,
            vol.Optional(ATTR_ZONE): cv.string,
        },
        "vorwerk_custom_cleaning",
    )

class VorwerkConnectedVacuum(CoordinatorEntity, StateVacuumEntity):
    """Representation of a Vorwerk Connected Vacuum."""

    # _attr_has_entity_name = True
    _attr_icon = "mdi:robot-vacuum"

    # Ersatz für dein SUPPORT_VORWERK
    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.LOCATE
    )

    def __init__(self, robot_state: VorwerkState, coordinator) -> None:
        super().__init__(coordinator)
        self._state: VorwerkState = robot_state
        self.robot = robot_state.robot

        self._attr_name = self.robot.name
        self._attr_unique_id = self.robot.serial
        self._robot_boundaries: list[dict[str, Any]] = []

    # ------------------
    # Status / Activity
    # ------------------

    @property
    def available(self) -> bool:
        return self._state.available

    @property
    def activity(self) -> VacuumActivity | None:
        s = self._state.state
        if s is None:
            return None
        if s == "cleaning":
            return VacuumActivity.CLEANING
        if s == "docked":
            return VacuumActivity.DOCKED
        if s == "idle":
            return VacuumActivity.IDLE
        if s == "paused":
            return VacuumActivity.PAUSED
        if s == "returning":
            return VacuumActivity.RETURNING
        if s == "error":
            return VacuumActivity.ERROR
        return None

    @property
    def battery_level(self) -> int | None:
        """Batterie – wird perspektivisch über den Sensor abgelöst."""
        level = self._state.battery_level
        try:
            return int(level) if level is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self._state.status is not None:
            data[ATTR_STATUS] = self._state.status
        return data

    @property
    def device_info(self):
        """Device info for robot."""
        return self._state.device_info

    # ------------------
    # Befehle
    # ------------------

    async def async_start(self):
        """Start cleaning or resume cleaning."""
        if not self._state:
            return
        try:
            if self._state.state in ("idle", "docked", None):
                await self.hass.async_add_executor_job(self.robot.start_cleaning)
            elif self._state.state == "paused":
                await self.hass.async_add_executor_job(self.robot.resume_cleaning)
        except Exception as ex:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    async def async_pause(self):
        """Pause the vacuum."""
        try:
            await self.hass.async_add_executor_job(self.robot.pause_cleaning)
        except Exception as ex:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    async def async_stop(self, **kwargs: Any):
        """Stop the vacuum cleaner."""
        try:
            await self.hass.async_add_executor_job(self.robot.stop_cleaning)
        except Exception as ex:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    async def async_return_to_base(self, **kwargs: Any):
        """Set the vacuum cleaner to return to the dock."""
        try:
            if self._state.state == "cleaning":
                await self.hass.async_add_executor_job(self.robot.pause_cleaning)
            await self.hass.async_add_executor_job(self.robot.send_to_base)
        except Exception as ex:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    async def async_locate(self, **kwargs: Any):
        """Locate the robot by making it emit a sound."""
        try:
            await self.hass.async_add_executor_job(self.robot.locate)
        except Exception as ex:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    async def async_clean_spot(self, **kwargs: Any):
        """Run a spot cleaning starting from the base."""
        try:
            await self.hass.async_add_executor_job(self.robot.start_spot_cleaning)
        except Exception as ex:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )

    # ------------------
    # Custom-Service: vorwerk.custom_cleaning
    # ------------------

    async def vorwerk_custom_cleaning(
        self,
        mode: int,
        navigation: int,
        category: int,
        zone: str | None = None,
    ) -> None:
        """Zone cleaning service call."""
        boundary_id: str | None = None

        if zone is not None:
            for boundary in self._robot_boundaries:
                if zone in boundary.get("name", ""):
                    boundary_id = boundary.get("id")
                    break
            if boundary_id is None:
                import logging

                logging.getLogger(__name__).error(
                    "Zone '%s' was not found for the robot '%s'", zone, self.entity_id
                )
                return

        try:
            await self.hass.async_add_executor_job(
                self.robot.start_cleaning, mode, navigation, category, boundary_id
            )
        except Exception as ex:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error(
                "Vorwerk vacuum connection error for '%s': %s", self.entity_id, ex
            )
