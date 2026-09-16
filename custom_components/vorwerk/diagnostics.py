"""Privacy-safe diagnostics for blocking Vorwerk cloud calls."""
from __future__ import annotations

import logging
from collections.abc import Callable
from time import monotonic
from typing import Any, TypeVar

from pybotvac.robot import Robot

_T = TypeVar("_T")


def _http_status_from_exception(err: Exception) -> int | None:
    """Return an HTTP status from an exception chain without logging its data."""
    current: BaseException | None = err
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        response = getattr(current, "response", None)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        current = current.__cause__ or current.__context__

    return None


def timed_cloud_call(
    logger: logging.Logger,
    operation: str,
    call: Callable[..., _T],
    *args: Any,
    context: str | None = None,
) -> _T:
    """Run a blocking cloud call and log only safe operational metadata."""
    target = f" for {context}" if context else ""
    started_at = monotonic()
    logger.debug("Starting Vorwerk %s%s", operation, target)

    try:
        result = call(*args)
    except Exception as err:
        status_code = _http_status_from_exception(err)
        status = f", HTTP status {status_code}" if status_code is not None else ""
        logger.warning(
            "Vorwerk %s%s failed after %.1f seconds (%s%s)",
            operation,
            target,
            monotonic() - started_at,
            type(err).__name__,
            status,
        )
        raise

    logger.debug(
        "Finished Vorwerk %s%s in %.1f seconds",
        operation,
        target,
        monotonic() - started_at,
    )
    return result


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
    return timed_cloud_call(
        logger,
        operation,
        call,
        *args,
        context=robot_log_id(robot),
    )
