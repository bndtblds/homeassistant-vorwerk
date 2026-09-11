"""Tests for the Vorwerk data update coordinator."""
from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pybotvac.exceptions import NeatoException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vorwerk import VorwerkRobotState
from custom_components.vorwerk.coordinator import VorwerkDataUpdateCoordinator
from custom_components.vorwerk.vacuum import VorwerkVacuumEntity


def make_coordinator(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot_state: VorwerkRobotState,
) -> VorwerkDataUpdateCoordinator:
    """Create a coordinator for a test."""
    return VorwerkDataUpdateCoordinator(
        hass,
        config_entry=config_entry,
        robot_state=robot_state,
    )


async def test_successful_update_runs_in_executor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot_state: VorwerkRobotState,
) -> None:
    """Test a successful blocking update outside the event loop thread."""
    event_loop_thread = threading.get_ident()
    update_thread: list[int] = []

    def update() -> None:
        update_thread.append(threading.get_ident())

    robot_state.update = update
    coordinator = make_coordinator(hass, config_entry, robot_state)

    assert await coordinator._async_update_data() is robot_state
    assert update_thread and update_thread[0] != event_loop_thread


async def test_api_error_becomes_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot_state: VorwerkRobotState,
) -> None:
    """Test a pybotvac communication error."""
    coordinator = make_coordinator(hass, config_entry, robot_state)
    failed_future = hass.loop.create_future()
    failed_future.set_exception(NeatoException("offline"))

    with (
        patch.object(
            hass,
            "async_add_executor_job",
            return_value=failed_future,
        ),
        pytest.raises(UpdateFailed, match="Error communicating"),
    ):
        await coordinator._async_update_data()


async def test_timeout_and_delayed_completion(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot_state: VorwerkRobotState,
) -> None:
    """Test timeout handling and cleanup after the executor finishes later."""
    release = threading.Event()

    def delayed_update() -> None:
        release.wait(timeout=1)
        raise NeatoException("late failure")

    robot_state.update = delayed_update
    coordinator = make_coordinator(hass, config_entry, robot_state)

    with (
        patch("custom_components.vorwerk.coordinator.ROBOT_API_TIMEOUT", 0.01),
        pytest.raises(UpdateFailed, match="Timed out updating"),
    ):
        await coordinator._async_update_data()

    assert coordinator._update_future is not None
    release.set()
    await asyncio.sleep(0.05)
    assert coordinator._update_future is None


async def test_overlapping_update_is_rejected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot_state: VorwerkRobotState,
) -> None:
    """Test that a second update does not create another executor job."""
    coordinator = make_coordinator(hass, config_entry, robot_state)
    pending = hass.loop.create_future()
    coordinator._update_future = pending

    with pytest.raises(UpdateFailed, match="Previous update"):
        await coordinator._async_update_data()

    pending.cancel()


def test_entity_unavailable_after_coordinator_failure(
    coordinator: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test entity availability after a failed coordinator update."""
    robot_state.robot_state = {"state": 1, "details": {}}
    coordinator.last_update_success = False

    assert VorwerkVacuumEntity(coordinator).available is False
