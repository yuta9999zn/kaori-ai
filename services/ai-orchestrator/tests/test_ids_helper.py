"""Unit tests for shared.ids — Python mirror of migration 104.

Covers RFC 9562 v7 layout, Crockford alphabet correctness, lex ordering
property, and rough collision sanity (1000-call no-dup).
"""
from __future__ import annotations

import re
import uuid

from ai_orchestrator.shared.ids import _CROCKFORD, uuid7, ulid


# ─── uuid7 ───────────────────────────────────────────────────────────

def test_uuid7_returns_uuid_instance():
    v = uuid7()
    assert isinstance(v, uuid.UUID)


def test_uuid7_version_is_seven():
    for _ in range(20):
        v = uuid7()
        assert v.version == 7


def test_uuid7_variant_is_rfc_4122():
    for _ in range(20):
        v = uuid7()
        assert v.variant == uuid.RFC_4122


def test_uuid7_timestamp_prefix_matches_now():
    """First 48 bits ≈ current unix_ms (within a few seconds)."""
    import time
    before = int(time.time() * 1000)
    v = uuid7()
    after = int(time.time() * 1000)
    ts = int.from_bytes(v.bytes[:6], "big")
    assert before - 5 <= ts <= after + 5


def test_uuid7_is_lexicographically_sortable_across_time():
    """Two UUIDs generated ~10ms apart must compare correctly as bytes."""
    import time
    a = uuid7()
    time.sleep(0.01)
    b = uuid7()
    assert a.bytes < b.bytes


def test_uuid7_no_dup_in_1000():
    """74 bits random tail → collision probability << 1 per 1000 calls."""
    ids = {uuid7() for _ in range(1000)}
    assert len(ids) == 1000


# ─── ulid ────────────────────────────────────────────────────────────

def test_ulid_length_26():
    assert len(ulid()) == 26


def test_ulid_only_crockford_chars():
    s = ulid()
    for ch in s:
        assert ch in _CROCKFORD, f"non-Crockford char in ULID: {ch!r}"


def test_ulid_alphabet_excludes_iluo():
    """Crockford base32 explicitly drops I, L, O, U to avoid ambiguity."""
    for forbidden in ("I", "L", "O", "U"):
        assert forbidden not in _CROCKFORD


def test_ulid_format_regex():
    """Whole string matches Crockford base32 pattern."""
    pattern = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
    for _ in range(20):
        assert pattern.match(ulid())


def test_ulid_timestamp_prefix_sorts_with_real_time():
    import time
    a = ulid()
    time.sleep(0.01)
    b = ulid()
    # Compare just the 10-char timestamp prefix (16-char random can flip
    # within same ms — but we slept past one ms boundary).
    assert a[:10] <= b[:10]


def test_ulid_no_dup_in_1000():
    ids = {ulid() for _ in range(1000)}
    assert len(ids) == 1000
