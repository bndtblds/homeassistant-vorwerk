"""The Vorwerk Kobold integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
import warnings

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

from pybotvac.exceptions import NeatoException, NeatoRobotException
from pybotvac.robot import Robot
from pybotvac.vorwerk import Vorwerk
import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, VacuumActivity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er, service
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    ACTION,
    ALERTS,
    DEFAULT_ENDPOINT,
    ERRORS,
    MODE,
    ROBOT_CLEANING_ACTIONS,
    ROBOT_STATE_BUSY,
    ROBOT_STATE_ERROR,
    ROBOT_STATE_IDLE,
    ROBOT_STATE_PAUSE,
    SERVICE_CUSTOM_CLEANING,
    VORWERK_DOMAIN,
    VORWERK_PLATFORMS,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)
from .coordinator import VorwerkDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = list(VORWERK_PLATFORMS)

CUSTOM_CLEANING_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional("mode", default=2): vol.All(vol.Coerce(int), vol.In((1, 2))),
        vol.Optional("navigation", default=1): vol.All(
            vol.Coerce(int), vol.In((1, 2, 3))
        ),
        vol.Optional("category", default=4): vol.All(
            vol.Coerce(int), vol.In((2, 4))
        ),
        vol.Optional("zone"): cv.string,
    }
)


@dataclass(slots=True)
class VorwerkRobotRuntime:
    """Runtime objects for a single robot."""

    state: VorwerkRobotState
    coordinator: VorwerkDataUpdateCoordinator


@dataclass(slots=True)
class VorwerkRuntimeData:
    """Runtime data stored on the config entry."""

    robots: list[VorwerkRobotRuntime]


VorwerkConfigEntry = ConfigEntry[VorwerkRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Vorwerk integration."""
    service.async_register_platform_entity_service(
        hass,
        VORWERK_DOMAIN,
        SERVICE_CUSTOM_CLEANING,
        entity_domain=VACUUM_DOMAIN,
        schema=CUSTOM_CLEANING_SCHEMA,
        func="async_custom_cleaning",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VorwerkConfigEntry) -> bool:
    """Set up Vorwerk from a config entry."""
    robots = await _async_create_robots(hass, entry.data[VORWERK_ROBOTS])
    await _async_migrate_schedule_switch_entities(hass, entry, robots)
    await _async_reset_entity_display_names(hass, entry, robots)
    runtime_robots: list[VorwerkRobotRuntime] = []

    for robot in robots:
        robot_state = VorwerkRobotState(robot)
        runtime_robots.append(
            VorwerkRobotRuntime(
                state=robot_state,
                coordinator=VorwerkDataUpdateCoordinator(hass, robot_state=robot_state),
            )
        )

    await asyncio.gather(
        *(
            robot_runtime.coordinator.async_config_entry_first_refresh()
            for robot_runtime in runtime_robots
        )
    )

    entry.runtime_data = VorwerkRuntimeData(robots=runtime_robots)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VorwerkConfigEntry) -> bool:
    """Unload a Vorwerk config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_migrate_schedule_switch_entities(
    hass: HomeAssistant,
    entry: VorwerkConfigEntry,
    robots: list[Robot],
) -> None:
    """Migrate legacy schedule switch entity registry entries.

    Older releases used the robot serial as the schedule switch unique ID.
    The current release uses `<serial>_schedule` so the entity ID becomes
    `switch.<robot_name>_schedule` and no longer collides conceptually with
    other robot entities.
    """
    entity_registry = er.async_get(hass)
    switch_entries = [
        registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if registry_entry.domain == "switch"
    ]

    entries_by_unique_id = {
        registry_entry.unique_id: registry_entry for registry_entry in switch_entries
    }

    for robot in robots:
        legacy_unique_id = robot.serial
        current_unique_id = f"{robot.serial}_schedule"

        legacy_entry = entries_by_unique_id.get(legacy_unique_id)
        current_entry = entries_by_unique_id.get(current_unique_id)

        if current_entry is not None:
            update_data: dict[str, Any] = {}

            if not current_entry.entity_id.endswith("_schedule"):
                update_data["new_entity_id"] = f"{current_entry.entity_id}_schedule"

            if current_entry.name == robot.name:
                update_data["name"] = None

            if update_data:
                entity_registry.async_update_entity(
                    current_entry.entity_id,
                    **update_data,
                )

            if legacy_entry is not None:
                entity_registry.async_remove(legacy_entry.entity_id)
            continue

        if legacy_entry is None:
            continue

        update_data: dict[str, Any] = {"new_unique_id": current_unique_id}
        if not legacy_entry.entity_id.endswith("_schedule"):
            update_data["new_entity_id"] = f"{legacy_entry.entity_id}_schedule"
        if legacy_entry.name == robot.name:
            update_data["name"] = None

        entity_registry.async_update_entity(
            legacy_entry.entity_id,
            **update_data,
        )


async def _async_reset_entity_display_names(
    hass: HomeAssistant,
    entry: VorwerkConfigEntry,
    robots: list[Robot],
) -> None:
    """Reset legacy explicit entity names so translations/default names apply."""
    entity_registry = er.async_get(hass)
    robots_by_serial = {robot.serial: robot for robot in robots}

    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        robot = _find_robot_for_registry_entry(robots_by_serial, registry_entry.unique_id)
        if robot is None or registry_entry.name is None:
            continue

        if registry_entry.domain == "switch" and _is_legacy_schedule_name(
            registry_entry.name, robot.name
        ):
            entity_registry.async_update_entity(registry_entry.entity_id, name=None)
            continue

        if registry_entry.domain == "sensor" and _is_legacy_battery_name(
            registry_entry.name, robot.name
        ):
            entity_registry.async_update_entity(registry_entry.entity_id, name=None)


def _find_robot_for_registry_entry(
    robots_by_serial: dict[str, Robot], unique_id: str
) -> Robot | None:
    """Return the robot that belongs to a registry entry unique ID."""
    for suffix in ("_schedule", "_battery"):
        if unique_id.endswith(suffix):
            return robots_by_serial.get(unique_id.removesuffix(suffix))
    return robots_by_serial.get(unique_id)


def _is_legacy_schedule_name(name: str, robot_name: str) -> bool:
    """Return whether a schedule entity name should be reset to the default."""
    return name in {
        robot_name,
        f"{robot_name} Schedule",
        f"{robot_name} Zeitplan",
        f"{robot_name} Planification",
    }


def _is_legacy_battery_name(name: str, robot_name: str) -> bool:
    """Return whether a battery entity name should be reset to the default."""
    return name in {
        robot_name,
        f"{robot_name} Battery",
        f"{robot_name} Batterie",
    }


async def _async_create_robots(
    hass: HomeAssistant, robot_configs: list[dict[str, Any]]
) -> list[Robot]:
    """Create Robot objects for all configured robots."""

    def create_robot(config: dict[str, Any]) -> Robot:
        return Robot(
            serial=config[VORWERK_ROBOT_SERIAL],
            secret=config[VORWERK_ROBOT_SECRET],
            traits=config.get(VORWERK_ROBOT_TRAITS, []),
            vendor=Vorwerk(),
            name=config[VORWERK_ROBOT_NAME],
            endpoint=config.get(VORWERK_ROBOT_ENDPOINT, DEFAULT_ENDPOINT),
        )

    try:
        return await asyncio.gather(
            *(
                hass.async_add_executor_job(create_robot, robot_config)
                for robot_config in robot_configs
            )
        )
    except NeatoException as err:
        raise ConfigEntryNotReady("Unable to connect to Vorwerk robots") from err


class VorwerkRobotState:
    """Wrap a pybotvac robot with Home Assistant friendly state helpers."""

    def __init__(self, robot: Robot) -> None:
        """Initialize the robot state wrapper."""
        self.robot = robot
        self.robot_state: dict[str, Any] = {}
        self.robot_info: dict[str, Any] = {}

    @property
    def available(self) -> bool:
        """Return whether the latest robot state is available."""
        return bool(self.robot_state)

    def update(self) -> None:
        """Refresh robot information and state from the API."""
        _LOGGER.debug("Refreshing Vorwerk robot state for %s", self.robot.name)
        self._update_robot_info()
        self._update_robot_state()

    def _update_robot_info(self) -> None:
        """Fetch static robot information once."""
        if self.robot_info:
            return

        try:
            response_data = self.robot.get_general_info().json().get("data")
        except NeatoRobotException:
            _LOGGER.warning("Unable to fetch robot information for %s", self.robot.name)
            return

        if isinstance(response_data, dict):
            self.robot_info = response_data

    def _update_robot_state(self) -> None:
        """Fetch the latest dynamic robot state."""
        had_state = self.available

        try:
            state = self.robot.state
        except NeatoRobotException as err:
            if had_state:
                _LOGGER.error(
                    "Vorwerk vacuum connection error for %s: %s",
                    self.robot.name,
                    err,
                )
            self.robot_state = {}
            return

        if isinstance(state, dict):
            self.robot_state = state
            _LOGGER.debug("Vorwerk state for %s: %s", self.robot.name, state)
            return

        self.robot_state = {}

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current Home Assistant vacuum activity."""
        if not self.available:
            return None

        state = self.robot_state.get("state")
        if self.charging or self.docked:
            return VacuumActivity.DOCKED
        if state == ROBOT_STATE_IDLE:
            return VacuumActivity.IDLE
        if state == ROBOT_STATE_BUSY:
            return (
                VacuumActivity.CLEANING
                if self.robot_state.get("action") in ROBOT_CLEANING_ACTIONS
                else VacuumActivity.RETURNING
            )
        if state == ROBOT_STATE_PAUSE:
            return VacuumActivity.PAUSED
        if state == ROBOT_STATE_ERROR:
            return VacuumActivity.ERROR
        return None

    @property
    def docked(self) -> bool | None:
        """Return whether the robot is docked."""
        if not self.available:
            return None

        details = self.robot_state.get("details", {})
        return self.robot_state.get("state") == ROBOT_STATE_IDLE and details.get(
            "isDocked", False
        )

    @property
    def charging(self) -> bool | None:
        """Return whether the robot is charging."""
        if not self.available:
            return None

        details = self.robot_state.get("details", {})
        return self.robot_state.get("state") == ROBOT_STATE_IDLE and details.get(
            "isCharging", False
        )

    @property
    def alert(self) -> str | None:
        """Return the translated robot alert, if any."""
        if not self.available:
            return None

        alert = self.robot_state.get("alert")
        if alert is None:
            return None
        return ALERTS.get(alert, str(alert))

    @property
    def status(self) -> str | None:
        """Return a human readable status string."""
        if not self.available:
            return None

        activity = self.activity
        if activity == VacuumActivity.ERROR:
            return self._error_status()
        if self.alert:
            return self.alert
        if activity == VacuumActivity.DOCKED:
            if self.charging:
                return "Charging"
            if self.docked:
                return "Docked"
        if activity == VacuumActivity.IDLE:
            return "Stopped"
        if activity == VacuumActivity.CLEANING:
            return self._cleaning_status()
        if activity == VacuumActivity.PAUSED:
            return "Paused"
        if activity == VacuumActivity.RETURNING:
            return "Returning"
        return None

    def _error_status(self) -> str | None:
        """Return the translated error status."""
        error = self.robot_state.get("error")
        if error is None:
            return None
        return ERRORS.get(error, str(error))

    def _cleaning_status(self) -> str:
        """Return a status string for an active cleaning run."""
        cleaning = self.robot_state.get("cleaning", {})
        status_items = [
            MODE.get(cleaning.get("mode")),
            ACTION.get(self.robot_state.get("action")),
        ]

        boundary_name = cleaning.get("boundary", {}).get("name")
        if boundary_name:
            status_items.append(boundary_name)

        return " ".join(item for item in status_items if item)

    @property
    def battery_level(self) -> int | None:
        """Return the battery level percentage."""
        if not self.available:
            return None

        charge = self.robot_state.get("details", {}).get("charge")
        if charge is None:
            return None

        try:
            return int(charge)
        except (TypeError, ValueError):
            return None

    @property
    def schedule_enabled(self) -> bool | None:
        """Return whether the robot schedule is enabled."""
        if not self.available:
            return None
        return bool(self.robot_state.get("details", {}).get("isScheduleEnabled"))

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device information."""
        battery_info = self.robot_info.get("battery", {})
        return DeviceInfo(
            identifiers={(VORWERK_DOMAIN, self.robot.serial)},
            manufacturer=battery_info.get("vendor"),
            model=self.robot_info.get("model"),
            name=self.robot.name,
            sw_version=self.robot_info.get("firmware"),
        )
