"""Diagnostic helpers for blocking Vorwerk robot calls."""
from __future__ import annotations

import logging
from collections.abc import Callable
from time import monotonic
from typing import Any, TypeVar

from pybotvac.robot import Robot

_T = TypeVar("_T")


def masked_robot_serial(robot: Robot) -> str:
    """Return only a masked suffix of a robot serial."""
    serial = str(robot.serial)
    return f"***{serial[-4:]}" if serial else "unknown"


def robot_log_id(robot: Robot) -> str:
    """Return a useful robot identifier without logging the full serial."""
    return f"{robot.name} ({masked_robot_serial(robot)})"


def timed_robot_call(
    logger: logging.Logger,
    robot: Robot,
    operation: str,
    call: Callable[..., _T],
    *args: Any,
) -> _T:
    """Run a blocking robot call and log its runtime and outcome."""
    robot_id = robot_log_id(robot)
    started_at = monotonic()
    logger.debug("Starting Vorwerk %s for %s", operation, robot_id)

    try:
        result = call(*args)
    except Exception:
        logger.warning(
            "Vorwerk %s failed for %s after %.1f seconds",
            operation,
            robot_id,
            monotonic() - started_at,
        )
        raise

    logger.debug(
        "Finished Vorwerk %s for %s in %.1f seconds",
        operation,
        robot_id,
        monotonic() - started_at,
    )
    return result
