from uuid import UUID

import pytest

from meridian.core import uuid7, uuid7_timestamp_ms


def test_uuid7_has_version_7_and_rfc_variant() -> None:
    value = uuid7()
    assert isinstance(value, UUID)
    assert value.version == 7
    assert value.variant == "specified in RFC 4122"


def test_uuid7_embeds_timestamp() -> None:
    value = uuid7(timestamp_ms=1_700_000_000_123)
    assert uuid7_timestamp_ms(value) == 1_700_000_000_123


def test_uuid7_is_time_ordered() -> None:
    earlier = uuid7(timestamp_ms=1_000)
    later = uuid7(timestamp_ms=2_000)
    assert earlier < later
    assert str(earlier) < str(later)


def test_uuid7_unique() -> None:
    ids = {uuid7() for _ in range(2000)}
    assert len(ids) == 2000


@pytest.mark.parametrize("bad", [-1, 1 << 48])
def test_uuid7_rejects_out_of_range_timestamp(bad: int) -> None:
    with pytest.raises(ValueError):
        uuid7(timestamp_ms=bad)


def test_timestamp_extraction_rejects_non_v7() -> None:
    with pytest.raises(ValueError):
        uuid7_timestamp_ms(UUID("12345678-1234-4234-8234-123456789abc"))
