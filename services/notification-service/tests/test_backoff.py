"""
Tests for ``backoff.py`` — the retry schedule for the notification
outbox poller.

This is a pure-function module so the tests are pure too: no I/O, no
clock. The schedule is documented in ``backoff.py``'s module docstring
and ALSO duplicated as a CASE expression inside the poller's SQL
(Postgres can't call into Python). The last test in this file pins
both copies in lockstep so a future refactor can't drift one without
the other.
"""
from backoff import _BACKOFF_SECONDS, backoff_seconds, schedule_total_seconds


# ─── Schedule values ─────────────────────────────────────────────

def test_attempts_zero_returns_zero_so_first_send_fires_immediately():
    # attempts=0 means "never tried" — caller must not delay the very
    # first send, otherwise reset-password emails would always wait at
    # least the first slot. Pin to 0.
    assert backoff_seconds(0) == 0


def test_attempts_one_through_four_match_documented_schedule():
    # Schedule exposed in the docstring: 0, 2, 8, 32, 128. Tests pin
    # each entry explicitly so a casual edit to the table (e.g.
    # "let's use 5 instead of 8") is loud.
    assert backoff_seconds(1) == 2
    assert backoff_seconds(2) == 8
    assert backoff_seconds(3) == 32
    assert backoff_seconds(4) == 128


def test_negative_attempts_treated_as_zero():
    # Defence in depth — the poller would never pass a negative value,
    # but a future caller (audit dashboard?) might. Better to clamp
    # than IndexError.
    assert backoff_seconds(-1) == 0
    assert backoff_seconds(-100) == 0


def test_attempts_beyond_schedule_clamps_to_last_value():
    # The poller checks ``attempts < max_attempts`` before calling, so
    # attempts >= len(schedule) shouldn't happen in practice. Still
    # clamp instead of crash so a stale row from a code-version
    # mismatch doesn't take the worker down.
    assert backoff_seconds(5) == 128
    assert backoff_seconds(99) == 128


def test_schedule_strictly_non_decreasing():
    # Backoff must never SHORTEN as attempts grow — that would defeat
    # the purpose. Pin the monotonicity invariant so any future tweak
    # is forced to keep this property.
    for i in range(1, len(_BACKOFF_SECONDS)):
        assert _BACKOFF_SECONDS[i] >= _BACKOFF_SECONDS[i - 1], (
            f"backoff[{i}]={_BACKOFF_SECONDS[i]} < backoff[{i-1}]="
            f"{_BACKOFF_SECONDS[i-1]} — schedule must be monotonic"
        )


def test_schedule_total_matches_documented_window():
    # The "≈ 3 minutes" claim in the module docstring is observable —
    # if a future tweak silently drops it to 30s, ops alerts that
    # assume the longer window will fire too eagerly. Pin total.
    assert schedule_total_seconds() == 170  # 0+2+8+32+128


# ─── SQL/Python schedule alignment ───────────────────────────────

def test_backoff_schedule_matches_sql_in_outbox_poller():
    """The poller's _claim_batch SQL has its own copy of the backoff
    schedule (Postgres can't call Python). Drift between the two would
    silently break retry semantics — Python would say "wait 32s" while
    SQL said "wait 8s", causing rows to be re-claimed too eagerly.

    We import the poller module, locate the SQL inside _claim_batch,
    and assert the CASE WHEN ... THEN ... pairs match the Python
    table 1-for-1.
    """
    import inspect
    import re

    from outbox_poller import OutboxPoller

    source = inspect.getsource(OutboxPoller._claim_batch)

    # Each pinned WHEN looks like ``WHEN N THEN M`` — pull them out.
    pinned = re.findall(r"WHEN\s+(\d+)\s+THEN\s+(\d+)", source)
    # Plus the ELSE clause for the catch-all tail.
    else_match = re.search(r"ELSE\s+(\d+)", source)
    assert else_match, "outbox_poller SQL must have an ELSE clause"

    for attempts_str, secs_str in pinned:
        attempts = int(attempts_str)
        secs = int(secs_str)
        assert backoff_seconds(attempts) == secs, (
            f"SQL CASE mismatch at attempts={attempts}: SQL says {secs}s, "
            f"backoff_seconds() says {backoff_seconds(attempts)}s. "
            "Update the WHEN list in outbox_poller._claim_batch when you "
            "change backoff.py."
        )

    # The ELSE branch should match the schedule's clamped tail value
    # (returned by backoff_seconds for any attempts >= len(schedule)).
    assert int(else_match.group(1)) == _BACKOFF_SECONDS[-1], (
        f"SQL ELSE clause says {else_match.group(1)}s but backoff schedule "
        f"tail is {_BACKOFF_SECONDS[-1]}s — keep the two in sync."
    )
