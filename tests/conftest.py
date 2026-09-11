"""Shared fixtures for the Vorwerk Kobold integration tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.vorwerk import VorwerkRobotState


@pytest.fixture
def robot() -> MagicMock:
    """Return a mocked Vorwerk robot."""
    robot = MagicMock()
    robot.name = "Upstairs"
    robot.serial = "VR300-1234"
    return robot


@pytest.fixture
def robot_state(robot: MagicMock) -> VorwerkRobotState:
    """Return a robot state wrapper."""
    return VorwerkRobotState(robot)


@pytest.fixture
def coordinator(robot_state: VorwerkRobotState) -> MagicMock:
    """Return a coordinator suitable for entity unit tests."""
    coordinator = MagicMock()
    coordinator.robot_state = robot_state
    coordinator.last_update_success = True
    return coordinator
