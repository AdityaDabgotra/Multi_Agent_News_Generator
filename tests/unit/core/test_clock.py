from datetime import UTC, datetime, timedelta

import pytest

from meridian.core import FixedClock, SystemClock


def test_system_clock_is_timezone_aware() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_fixed_clock_returns_fixed_time_and_advances() -> None:
    start = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
    clock = FixedClock(start)
    assert clock.now() == start
    clock.advance(timedelta(minutes=5))
    assert clock.now() == start + timedelta(minutes=5)


def test_fixed_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 11, 10, 12, 0))
