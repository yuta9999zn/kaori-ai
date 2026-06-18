-- =====================================================================
-- 104_uuid_v7_and_ulid_functions.sql — ADR-0029 — ID strategy refresh
--
-- Adds two ID-generator functions for new tables going forward. Existing
-- UUIDv4 columns are kept as-is (no data migration).
--
--   gen_uuid_v7()  → UUID                 (RFC 9562 v7 layout)
--   gen_ulid()     → TEXT(26)             (Crockford base32, ULID spec)
--
-- Both are time-prefixed → B-tree insert locality improves, index
-- fragmentation drops vs random v4. Used by:
--
--   • new tables Phase 2.9+        → DEFAULT gen_uuid_v7()
--   • external-facing public IDs   → DEFAULT gen_ulid()    (URLs, logs)
--
-- Implementation notes
-- --------------------
-- gen_uuid_v7 layout (RFC 9562):
--   bytes  0..5  → 48-bit unix_ts_ms (big-endian)
--   byte   6     → version nibble = 0x7 in high 4 bits + 4 random bits
--   byte   7     → 8 random bits
--   byte   8     → variant = 10xxxxxx (RFC 4122) + 6 random bits
--   bytes  9..15 → 56 random bits
--   total random: 4 + 8 + 6 + 56 = 74 bits → collision-safe at scale
--
-- gen_ulid layout (ULID spec):
--   chars  0..9   → 48-bit unix_ts_ms in Crockford base32 (msb first)
--   chars 10..25  → 80 bits random in Crockford base32
--   alphabet     0123456789ABCDEFGHJKMNPQRSTVWXYZ  (no I/L/O/U)
--
-- Monotonicity caveat
-- -------------------
-- Neither function is strictly monotonic within a single millisecond
-- (no shared session counter). Same-ms inserts are ordered by random
-- tail. For our access patterns (decision audit, workflow run public_id,
-- adoption snapshots) this is fine — the 74/80-bit random tails make
-- intra-ms collisions astronomically unlikely and the timestamp prefix
-- still gives the B-tree locality benefit we want. If a future caller
-- needs strict monotonicity, add a per-session counter in the app layer
-- (see services/ai-orchestrator/shared/ids.py).
-- =====================================================================

BEGIN;

-- ─── gen_uuid_v7() ───────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION gen_uuid_v7() RETURNS UUID
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    ts_ms      BIGINT;
    rand_bytes BYTEA;
    uuid_bytes BYTEA;
    i          INT;
BEGIN
    ts_ms      := (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT;
    rand_bytes := gen_random_bytes(10);
    uuid_bytes := '\x00000000000000000000000000000000'::BYTEA;

    -- 48-bit timestamp, big-endian, bytes 0..5
    uuid_bytes := set_byte(uuid_bytes, 0, ((ts_ms >> 40) & 255)::INT);
    uuid_bytes := set_byte(uuid_bytes, 1, ((ts_ms >> 32) & 255)::INT);
    uuid_bytes := set_byte(uuid_bytes, 2, ((ts_ms >> 24) & 255)::INT);
    uuid_bytes := set_byte(uuid_bytes, 3, ((ts_ms >> 16) & 255)::INT);
    uuid_bytes := set_byte(uuid_bytes, 4, ((ts_ms >>  8) & 255)::INT);
    uuid_bytes := set_byte(uuid_bytes, 5, ( ts_ms        & 255)::INT);

    -- 10 random bytes into positions 6..15
    FOR i IN 0..9 LOOP
        uuid_bytes := set_byte(uuid_bytes, 6 + i, get_byte(rand_bytes, i));
    END LOOP;

    -- Stamp version (0x7) into high nibble of byte 6
    uuid_bytes := set_byte(
        uuid_bytes, 6,
        ((get_byte(uuid_bytes, 6) & 15) | 112)::INT   -- 0x70 = 0111 0000
    );

    -- Stamp variant (10xxxxxx) into high bits of byte 8
    uuid_bytes := set_byte(
        uuid_bytes, 8,
        ((get_byte(uuid_bytes, 8) & 63) | 128)::INT   -- 0x80 = 1000 0000
    );

    RETURN encode(uuid_bytes, 'hex')::UUID;
END;
$$;

COMMENT ON FUNCTION gen_uuid_v7() IS
    'ADR-0029 — UUIDv7 (RFC 9562). Time-prefixed, B-tree friendly. '
    'Default for new tables Phase 2.9+. Existing v4 columns untouched.';


-- ─── gen_ulid() ──────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION gen_ulid() RETURNS TEXT
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    alphabet  CONSTANT TEXT := '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
    ts_ms     BIGINT;
    rnd       BYTEA;
    accum     BIGINT;
    ts_part   TEXT := '';
    rand_part TEXT := '';
    i         INT;
BEGIN
    ts_ms := (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT;

    -- 48-bit timestamp → 10 Crockford base32 chars (5 bits/char, msb first)
    -- Top 2 bits of char[0] are forced zero (timestamp fits in 48 bits,
    -- not 50 — valid until year 10889 AD).
    FOR i IN 0..9 LOOP
        ts_part := ts_part || substr(
            alphabet,
            (((ts_ms >> (45 - i * 5)) & 31))::INT + 1,
            1
        );
    END LOOP;

    -- 80 bits random → 16 Crockford base32 chars
    -- Split into two 40-bit halves so each fits in a BIGINT accumulator.
    rnd := gen_random_bytes(10);

    accum := 0;
    FOR i IN 0..4 LOOP
        accum := (accum << 8) | get_byte(rnd, i);
    END LOOP;
    FOR i IN 0..7 LOOP
        rand_part := rand_part || substr(
            alphabet,
            (((accum >> (35 - i * 5)) & 31))::INT + 1,
            1
        );
    END LOOP;

    accum := 0;
    FOR i IN 5..9 LOOP
        accum := (accum << 8) | get_byte(rnd, i);
    END LOOP;
    FOR i IN 0..7 LOOP
        rand_part := rand_part || substr(
            alphabet,
            (((accum >> (35 - i * 5)) & 31))::INT + 1,
            1
        );
    END LOOP;

    RETURN ts_part || rand_part;
END;
$$;

COMMENT ON FUNCTION gen_ulid() IS
    'ADR-0029 — ULID (Crockford base32, 26 chars). For external-facing '
    'public IDs (URLs, log lines, customer-visible references). Stored '
    'as TEXT(26). Lexicographically time-sortable.';


-- ─── Grants ──────────────────────────────────────────────────────────
-- Both functions are SECURITY INVOKER (default) — no special role needed.
-- App role kaori_app uses them via column DEFAULTs in new migrations.

GRANT EXECUTE ON FUNCTION gen_uuid_v7() TO PUBLIC;
GRANT EXECUTE ON FUNCTION gen_ulid()    TO PUBLIC;

COMMIT;
