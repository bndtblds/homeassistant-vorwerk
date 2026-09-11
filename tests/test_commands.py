"""Tests for Vorwerk robot command execution."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.vacuum import VacuumActivity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.vorwerk import VorwerkRobotState
from custom_components.vorwerk.switch import VorwerkScheduleSwitch
from custom_components.vorwerk.vacuum import VorwerkVacuumEntity


def attach_hass(entity: VorwerkVacuumEntity | VorwerkScheduleSwitch, hass) -> None:
    """Attach Home Assistant to an entity."""
    entity.hass = hass


async def test_robot_command_uses_executor_and_refreshes(
    hass: HomeAssistant,
    coordinator: MagicMock,
) -> None:
    """Test successful command execution and coordinator refresh."""
    entity = VorwerkVacuumEntity(coordinator)
    attach_hass(entity, hass)
    command = MagicMock()
    completed = hass.loop.create_future()
    completed.set_result(None)
    coordinator.async_request_refresh = AsyncMock()

    with patch.object(
        hass,
        "async_add_executor_job",
        return_value=completed,
    ) as executor_job:
        await entity._async_call_robot_command(command, 1, "argument")

    executor_job.assert_called_once_with(command, 1, "argument")
    coordinator.async_request_refresh.assert_awaited_once_with()


async def test_robot_command_can_skip_refresh(
    hass: HomeAssistant,
    coordinator: MagicMock,
) -> None:
    """Test suppression of the post-command refresh."""
    entity = VorwerkVacuumEntity(coordinator)
    attach_hass(entity, hass)
    completed = hass.loop.create_future()
    completed.set_result(None)
    coordinator.async_request_refresh = AsyncMock()

    with patch.object(hass, "async_add_executor_job", return_value=completed):
        await entity._async_call_robot_command(MagicMock(), refresh=False)

    coordinator.async_request_refresh.assert_not_awaited()


async def test_robot_command_timeout(
    hass: HomeAssistant,
    coordinator: MagicMock,
) -> None:
    """Test conversion of command timeouts to Home Assistant errors."""
    entity = VorwerkVacuumEntity(coordinator)
    attach_hass(entity, hass)
    pending = hass.loop.create_future()

    with (
        patch.object(hass, "async_add_executor_job", return_value=pending),
        patch("custom_components.vorwerk.entity.ROBOT_API_TIMEOUT", 0.01),
        pytest.raises(HomeAssistantError),
    ):
        await entity._async_call_robot_command(MagicMock())


async def test_robot_command_api_error(
    hass: HomeAssistant,
    coordinator: MagicMock,
) -> None:
    """Test conversion of API failures to Home Assistant errors."""
    entity = VorwerkVacuumEntity(coordinator)
    attach_hass(entity, hass)
    failed = hass.loop.create_future()
    failed.set_exception(RuntimeError("offline"))

    with (
        patch.object(hass, "async_add_executor_job", return_value=failed),
        pytest.raises(HomeAssistantError),
    ):
        await entity._async_call_robot_command(MagicMock())


@pytest.mark.parametrize(
    ("method_name", "robot_method"),
    [
        ("async_pause", "pause_cleaning"),
        ("async_stop", "stop_cleaning"),
        ("async_locate", "locate"),
        ("async_clean_spot", "start_spot_cleaning"),
    ],
)
async def test_vacuum_commands(
    coordinator: MagicMock,
    method_name: str,
    robot_method: str,
) -> None:
    """Test direct vacuum command dispatch."""
    entity = VorwerkVacuumEntity(coordinator)
    entity._async_call_robot_command = AsyncMock()

    await getattr(entity, method_name)()

    entity._async_call_robot_command.assert_awaited_once_with(
        getattr(entity.robot, robot_method)
    )


async def test_vacuum_start_and_resume(
    coordinator: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test start and resume command selection."""
    entity = VorwerkVacuumEntity(coordinator)
    entity._async_call_robot_command = AsyncMock()

    robot_state.robot_state = {"state": 1, "details": {}}
    await entity.async_start()
    entity._async_call_robot_command.assert_awaited_once_with(
        entity.robot.start_cleaning
    )

    entity._async_call_robot_command.reset_mock()
    robot_state.robot_state = {"state": 3, "details": {}}
    assert entity.activity is VacuumActivity.PAUSED
    await entity.async_start()
    entity._async_call_robot_command.assert_awaited_once_with(
        entity.robot.resume_cleaning
    )


async def test_return_to_base_pauses_cleaning(
    coordinator: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test return-to-base command sequencing while cleaning."""
    robot_state.robot_state = {"state": 2, "action": 1, "details": {}}
    entity = VorwerkVacuumEntity(coordinator)
    entity._async_call_robot_command = AsyncMock()

    await entity.async_return_to_base()

    assert entity._async_call_robot_command.await_args_list == [
        ((entity.robot.pause_cleaning,), {"refresh": False}),
        ((entity.robot.send_to_base,), {}),
    ]


@pytest.mark.parametrize(
    ("method_name", "robot_method"),
    [
        ("async_turn_on", "enable_schedule"),
        ("async_turn_off", "disable_schedule"),
    ],
)
async def test_schedule_commands(
    coordinator: MagicMock,
    method_name: str,
    robot_method: str,
) -> None:
    """Test schedule command dispatch."""
    entity = VorwerkScheduleSwitch(coordinator)
    entity._async_call_robot_command = AsyncMock()

    await getattr(entity, method_name)()

    entity._async_call_robot_command.assert_awaited_once_with(
        getattr(entity.robot, robot_method)
    )
