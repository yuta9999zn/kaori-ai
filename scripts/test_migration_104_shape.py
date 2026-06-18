"""Shape tests for migration 104 — gen_uuid_v7 + gen_ulid (ADR-0029).

Pure-Python regex assertions over the SQL text. Functional tests
(actually executing the plpgsql against a live Postgres) live in
services/ai-orchestrator/tests/test_uuid_v7_and_ulid.py once the
shared.ids helper lands.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO    = Path(__file__).resolve().parent.parent
MIG_DIR = REPO / "infrastructure" / "postgres" / "migrations"
MIG_104 = (MIG_DIR / "104_uuid_v7_and_ulid_functions.sql").read_text(encoding="utf-8")


def _strip(sql: str) -> str:
    """Strip SQL comments so regex assertions don't match comment prose."""
    out, in_block = [], False
    for line in sql.splitlines():
        if in_block:
            end = line.find("*/")
            if end == -1:
                continue
            line = line[end + 2:]
            in_block = False
        while True:
            start = line.find("/*")
            if start == -1:
                break
            end = line.find("*/", start + 2)
            if end == -1:
                line = line[:start]
                in_block = True
                break
            line = line[:start] + line[end + 2:]
        out.append(line.split("--", 1)[0])
    return "\n".join(out)


M = _strip(MIG_104)


# ─── gen_uuid_v7 shape ───────────────────────────────────────────────

def test_creates_gen_uuid_v7_function():
    assert re.search(
        r"CREATE OR REPLACE FUNCTION gen_uuid_v7\(\)\s+RETURNS\s+UUID",
        M, re.IGNORECASE,
    )


def test_uuid_v7_is_plpgsql_volatile():
    body = re.search(
        r"CREATE OR REPLACE FUNCTION gen_uuid_v7.*?\$\$;",
        M, re.DOTALL | re.IGNORECASE,
    )
    assert body
    assert re.search(r"LANGUAGE\s+plpgsql", body.group(0), re.IGNORECASE)
    assert re.search(r"\bVOLATILE\b", body.group(0), re.IGNORECASE)


def test_uuid_v7_uses_clock_timestamp_ms():
    """Must use clock_timestamp() (per-statement) not now() (per-tx)
    so multiple rows inserted in one tx still get distinct timestamps."""
    body = re.search(
        r"CREATE OR REPLACE FUNCTION gen_uuid_v7.*?\$\$;",
        M, re.DOTALL | re.IGNORECASE,
    )
    assert body
    assert "clock_timestamp()" in body.group(0)
    assert re.search(r"\* 1000", body.group(0))


def test_uuid_v7_stamps_version_nibble_seven():
    """Version 7 = 0x70 in high nibble of byte 6."""
    assert re.search(r"set_byte\(\s*uuid_bytes,\s*6,", M)
    # 0x70 = 112, mask 0x0F = 15
    assert re.search(r"&\s*15\s*\)\s*\|\s*112", M)


def test_uuid_v7_stamps_rfc4122_variant():
    """Variant 10xx = 0x80 in byte 8, mask 0x3F = 63."""
    assert re.search(r"set_byte\(\s*uuid_bytes,\s*8,", M)
    assert re.search(r"&\s*63\s*\)\s*\|\s*128", M)


def test_uuid_v7_uses_pgcrypto_random_bytes():
    assert re.search(r"gen_random_bytes\(\s*10\s*\)", M)


# ─── gen_ulid shape ──────────────────────────────────────────────────

def test_creates_gen_ulid_function():
    assert re.search(
        r"CREATE OR REPLACE FUNCTION gen_ulid\(\)\s+RETURNS\s+TEXT",
        M, re.IGNORECASE,
    )


def test_ulid_uses_crockford_alphabet():
    """Crockford base32 — must exclude I, L, O, U."""
    m = re.search(r"alphabet\s+CONSTANT\s+TEXT\s*:=\s*'([^']+)'", M)
    assert m, "alphabet constant not found"
    alphabet = m.group(1)
    assert len(alphabet) == 32
    for forbidden in ("I", "L", "O", "U"):
        assert forbidden not in alphabet, f"{forbidden} must not appear in Crockford alphabet"
    # Must have digits 0-9 + A-Z minus I/L/O/U
    for ch in "0123456789ABCDEFGHJKMNPQRSTVWXYZ":
        assert ch in alphabet


def test_ulid_emits_26_chars():
    """10 timestamp chars + 16 random chars = 26 total."""
    # Two loops of 0..7 for random part = 16 chars
    rand_loops = re.findall(r"FOR i IN 0\.\.7 LOOP", M)
    assert len(rand_loops) == 2, "expected two 8-iteration random loops"
    # One loop of 0..9 for timestamp = 10 chars
    ts_loops = re.findall(r"FOR i IN 0\.\.9 LOOP", M)
    assert len(ts_loops) >= 1


def test_ulid_uses_clock_timestamp():
    body = re.search(
        r"CREATE OR REPLACE FUNCTION gen_ulid.*?\$\$;",
        M, re.DOTALL | re.IGNORECASE,
    )
    assert body
    assert "clock_timestamp()" in body.group(0)


def test_ulid_random_uses_pgcrypto_10_bytes():
    body = re.search(
        r"CREATE OR REPLACE FUNCTION gen_ulid.*?\$\$;",
        M, re.DOTALL | re.IGNORECASE,
    )
    assert body
    assert re.search(r"gen_random_bytes\(\s*10\s*\)", body.group(0))


# ─── Grants + transactional wrapper ──────────────────────────────────

def test_wrapped_in_begin_commit():
    assert re.search(r"\bBEGIN\s*;", M)
    assert re.search(r"\bCOMMIT\s*;", M)


def test_grants_execute_to_public():
    assert re.search(r"GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+gen_uuid_v7\(\)\s+TO\s+PUBLIC", M, re.IGNORECASE)
    assert re.search(r"GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+gen_ulid\(\)\s+TO\s+PUBLIC",    M, re.IGNORECASE)


def test_functions_have_comments():
    """Both functions document ADR-0029 in COMMENT ON FUNCTION."""
    assert re.search(r"COMMENT\s+ON\s+FUNCTION\s+gen_uuid_v7\(\)\s+IS\s+'.*ADR-0029", MIG_104, re.IGNORECASE | re.DOTALL)
    assert re.search(r"COMMENT\s+ON\s+FUNCTION\s+gen_ulid\(\)\s+IS\s+'.*ADR-0029", MIG_104, re.IGNORECASE | re.DOTALL)
