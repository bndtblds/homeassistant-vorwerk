"""Tests for Vorwerk blocking-call diagnostics."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from custom_components.vorwerk.diagnostics import (
    masked_robot_serial,
    robot_log_id,
    timed_robot_call,
)


def test_robot_log_id_masks_serial(robot: MagicMock) -> None:
    """Test that diagnostics never expose the complete robot serial."""
    assert masked_robot_serial(robot) == "***1234"
    assert robot_log_id(robot) == "Upstairs (***1234)"
    assert "VR300-1234" not in robot_log_id(robot)


def test_timed_robot_call_logs_start_and_finish(
    caplog: pytest.LogCaptureFixture,
    robot: MagicMock,
) -> None:
    """Test successful blocking-call timing diagnostics."""
    logger = logging.getLogger("test.vorwerk.diagnostics")
    call = MagicMock(return_value="result")

    with (
        caplog.at_level(logging.DEBUG, logger=logger.name),
        patch(
            "custom_components.vorwerk.diagnostics.monotonic",
            side_effect=[10.0, 12.5],
        ),
    ):
        assert timed_robot_call(logger, robot, "get_robot_state", call) == "result"

    assert "Starting Vorwerk get_robot_state for Upstairs (***1234)" in caplog.text
    assert (
        "Finished Vorwerk get_robot_state for Upstairs (***1234) in 2.5 seconds"
        in caplog.text
    )
    assert "VR300-1234" not in caplog.text


def test_timed_robot_call_logs_failure(
    caplog: pytest.LogCaptureFixture,
    robot: MagicMock,
) -> None:
    """Test failed blocking-call timing diagnostics."""
    logger = logging.getLogger("test.vorwerk.diagnostics")
    call = MagicMock(side_effect=RuntimeError("offline"))

    with (
        caplog.at_level(logging.WARNING, logger=logger.name),
        patch(
            "custom_components.vorwerk.diagnostics.monotonic",
            side_effect=[20.0, 23.0],
        ),
        pytest.raises(RuntimeError, match="offline"),
    ):
        timed_robot_call(logger, robot, "get_robot_state", call)

    assert (
        "Vorwerk get_robot_state failed for Upstairs (***1234) after 3.0 seconds"
        in caplog.text
    )
