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


def test_timed_robot_call_logs_timing_only_at_debug(
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

    timing_records = [
        record for record in caplog.records if "2.5 seconds" in record.message
    ]
    assert len(timing_records) == 1
    assert timing_records[0].levelno == logging.DEBUG
    assert "VR300-1234" not in caplog.text


def test_repeated_robot_failures_warn_once_until_success(
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

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        with pytest.raises(RuntimeError, match="offline"):
            timed_robot_call(logger, robot, "get_robot_state", call)
        with pytest.raises(RuntimeError, match="offline"):
            timed_robot_call(logger, robot, "get_robot_state", call)
        timed_robot_call(logger, robot, "get_robot_state", call)
        with pytest.raises(RuntimeError, match="offline"):
            timed_robot_call(logger, robot, "get_robot_state", call)

    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and "get_robot_state" in record.message
    ]
    assert len(warnings) == 2


def test_failure_warning_omits_timing_and_sensitive_data(
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

    warning = next(record for record in caplog.records if record.levelno == logging.WARNING)
    assert "HTTP status 403" in warning.message
    assert "seconds" not in warning.message
    assert any(
        record.levelno == logging.DEBUG and "1.5 seconds" in record.message
        for record in caplog.records
    )
    assert "owner@example.com" not in caplog.text
    assert "123456" not in caplog.text
    assert "secret response body" not in caplog.text
