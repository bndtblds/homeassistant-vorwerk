"""Tests for Vorwerk blocking-call diagnostics."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from custom_components.vorwerk.diagnostics import (
    _ACTIVE_FAILURES,
    masked_robot_serial,
    robot_log_id,
    timed_cloud_call,
    timed_robot_call,
)


@pytest.fixture(autouse=True)
def clear_active_failures() -> None:
    """Keep failure-suppression state isolated between tests."""
    _ACTIVE_FAILURES.clear()


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
        "Vorwerk get_robot_state for Upstairs (***1234) failed after 3.0 seconds"
        in caplog.text
    )


def test_timed_robot_call_suppresses_repeated_warnings_until_success(
    caplog: pytest.LogCaptureFixture,
    robot: MagicMock,
) -> None:
    """Test that repeated polling failures do not flood warning logs."""
    logger = logging.getLogger("test.vorwerk.repeated_diagnostics")
    call = MagicMock(
        side_effect=[
            RuntimeError("offline"),
            RuntimeError("offline"),
            None,
            RuntimeError("offline"),
        ]
    )

    with (
        caplog.at_level(logging.DEBUG, logger=logger.name),
        patch(
            "custom_components.vorwerk.diagnostics.monotonic",
            side_effect=[10.0, 11.0, 20.0, 21.0, 30.0, 31.0, 40.0, 41.0],
        ),
    ):
        with pytest.raises(RuntimeError, match="offline"):
            timed_robot_call(logger, robot, "get_robot_state", call)
        with pytest.raises(RuntimeError, match="offline"):
            timed_robot_call(logger, robot, "get_robot_state", call)
        timed_robot_call(logger, robot, "get_robot_state", call)
        with pytest.raises(RuntimeError, match="offline"):
            timed_robot_call(logger, robot, "get_robot_state", call)

    failure_records = [
        record
        for record in caplog.records
        if "Vorwerk get_robot_state" in record.message
        and "failed after" in record.message
    ]
    assert [record.levelno for record in failure_records] == [
        logging.WARNING,
        logging.DEBUG,
        logging.WARNING,
    ]


def test_timed_cloud_call_logs_http_status_without_sensitive_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test safe HTTP failure metadata without arguments or response content."""
    logger = logging.getLogger("test.vorwerk.auth_diagnostics")
    response = MagicMock(status_code=403)
    error = RuntimeError("secret response body")
    error.response = response
    call = MagicMock(side_effect=error)

    with (
        caplog.at_level(logging.DEBUG, logger=logger.name),
        patch(
            "custom_components.vorwerk.diagnostics.monotonic",
            side_effect=[30.0, 31.5],
        ),
        pytest.raises(RuntimeError, match="secret response body"),
    ):
        timed_cloud_call(
            logger,
            "OTP token exchange",
            call,
            "owner@example.com",
            "123456",
        )

    assert (
        "Vorwerk OTP token exchange failed after 1.5 seconds "
        "(RuntimeError, HTTP status 403)" in caplog.text
    )
    assert "owner@example.com" not in caplog.text
    assert "123456" not in caplog.text
    assert "secret response body" not in caplog.text
