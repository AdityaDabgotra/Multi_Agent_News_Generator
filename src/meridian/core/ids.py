"""UUIDv7 generation (time-ordered identifiers).

Layout (RFC 9562): 48-bit unix-ms timestamp | 4-bit version (7) | 12-bit rand_a |
2-bit variant (0b10) | 62-bit rand_b. Time-ordered IDs keep database indexes compact.
"""

from __future__ import annotations

import os
import time
from uuid import UUID

_MAX_MS = (1 << 48) - 1


def uuid7(*, timestamp_ms: int | None = None) -> UUID:
    """Return a new UUIDv7. ``timestamp_ms`` is injectable for deterministic tests."""
    ms = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    if not 0 <= ms <= _MAX_MS:
        raise ValueError("timestamp_ms must fit in 48 bits")
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    rand_a = (rand >> 68) & 0xFFF  # top 12 bits
    rand_b = rand & ((1 << 62) - 1)  # low 62 bits
    value = (ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return UUID(int=value)


def uuid7_timestamp_ms(value: UUID) -> int:
    """Extract the embedded unix-millisecond timestamp from a UUIDv7."""
    if value.version != 7:
        raise ValueError("not a UUIDv7")
    return value.int >> 80
