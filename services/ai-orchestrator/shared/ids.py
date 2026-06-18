"""ID generators — UUIDv7 + ULID (ADR-0029).

Pure-Python mirrors of plpgsql `gen_uuid_v7()` and `gen_ulid()` from
migration 104. Use these when an INSERT needs to know the ID *before*
the row is written (returning-clause fetch is round-trip + breaks the
DEFAULT path for some ORMs). For straight INSERTs, prefer the DB-side
DEFAULT — see ADR-0029 "writer-path coupling" section.

Layout (matches RFC 9562 v7 and ULID spec):
    uuid7  → 48-bit unix_ts_ms || ver=7 (4b) || 74 random bits + variant=10
    ulid   → 10-char Crockford base32 timestamp || 16-char random
"""
from __future__ import annotations

import os
import time
import uuid

__all__ = ["uuid7", "ulid"]


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # no I, L, O, U


def _unix_ms() -> int:
    """48-bit Unix timestamp in milliseconds."""
    return int(time.time() * 1000) & ((1 << 48) - 1)


def uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7. Time-prefixed → B-tree friendly.

    Returns a `uuid.UUID` (same type as `uuid.uuid4()`) so callers can
    cast freely to str / bytes / int. Not strictly monotonic within a
    single millisecond — see migration 104 header.
    """
    ts_ms = _unix_ms()
    rand = os.urandom(10)

    # Build 16 bytes: 6 bytes timestamp || 10 bytes random
    buf = bytearray(16)
    buf[0] = (ts_ms >> 40) & 0xFF
    buf[1] = (ts_ms >> 32) & 0xFF
    buf[2] = (ts_ms >> 24) & 0xFF
    buf[3] = (ts_ms >> 16) & 0xFF
    buf[4] = (ts_ms >>  8) & 0xFF
    buf[5] =  ts_ms        & 0xFF
    buf[6:16] = rand

    # Stamp version 7 (high nibble of byte 6)
    buf[6] = (buf[6] & 0x0F) | 0x70
    # Stamp RFC 4122 variant (high bits of byte 8)
    buf[8] = (buf[8] & 0x3F) | 0x80

    return uuid.UUID(bytes=bytes(buf))


def ulid() -> str:
    """ULID — 26-char Crockford base32. For external-facing public IDs.

    First 10 chars = ms timestamp (lexicographically sortable).
    Last 16 chars = 80 bits of random entropy.
    """
    ts_ms = _unix_ms()
    rand = int.from_bytes(os.urandom(10), "big")

    # Timestamp half: 48 bits → 10 chars × 5 bits each (top 2 bits of
    # char[0] are zero; ULID spec allows up to 50 bits = year 10889 AD).
    ts_chars = []
    for i in range(10):
        ts_chars.append(_CROCKFORD[(ts_ms >> (45 - i * 5)) & 0x1F])

    # Random half: 80 bits → 16 chars × 5 bits each.
    rand_chars = []
    for i in range(16):
        rand_chars.append(_CROCKFORD[(rand >> (75 - i * 5)) & 0x1F])

    return "".join(ts_chars) + "".join(rand_chars)
