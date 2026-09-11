"""Shared fixtures for the Vorwerk Kobold integration tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vorwerk import VorwerkRobotState
from custom_components.vorwerk.const import (
    VORWERK_DOMAIN,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in tests."""


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


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a mocked Vorwerk config entry."""
    return MockConfigEntry(
        domain=VORWERK_DOMAIN,
        unique_id="owner@example.com",
        title="owner@example.com",
        data={
            "email": "owner@example.com",
            VORWERK_ROBOTS: [
                {
                    VORWERK_ROBOT_NAME: "Upstairs",
                    VORWERK_ROBOT_SERIAL: "VR300-1234",
                    VORWERK_ROBOT_SECRET: "not-a-real-secret",
                    VORWERK_ROBOT_TRAITS: ["maps"],
                    VORWERK_ROBOT_ENDPOINT: "https://example.invalid",
                }
            ],
        },
    )
