"""
Retry backoff schedule for the notification outbox poller.

Pure function — no I/O, no clock — so the math can be unit-tested
without faking time. The poller imports ``backoff_seconds`` and adds
the result to ``last_attempt_at`` to compute "earliest time this row
is eligible to retry".

Schedule rationale
==================
Five total attempts. Four retry waits chosen to cover the common SMTP
transient outage shapes:

  attempts=0 →   0s   (never tried — fire on the very next poll tick)
  attempts=1 →   2s   (smarthost connection refusal, instant retry)
  attempts=2 →   8s   (TLS handshake stall, smarthost queue rebuild)
  attempts=3 →  32s   (smarthost reload, DNS flap)
  attempts=4 → 128s   (longer relay outage; last chance before dead)
  attempts≥5 → row goes to status='dead' (caller checks max_attempts
               separately; this function still returns the cap value
               so callers can log "would have waited Ns" defensively)

Total worst-case wait window: 0+2+8+32+128 = 170s ≈ 2 min 50 s. Long
enough to ride out the typical 30 s – 2 min smarthost wobble; short
enough that a reset-password user gets the email within ~3 min when
SMTP recovers, vs. losing it entirely under the old direct-HTTP path.
"""
from __future__ import annotations

# 0-indexed by attempts ALREADY MADE (and failed). attempts=0 means
# "never tried" so the wait is 0 — the row is fired on the next poll
# tick. Anything beyond the table length clamps to the last value so
# callers don't need to bounds-check.
_BACKOFF_SECONDS = [0, 2, 8, 32, 128]


def backoff_seconds(attempts: int) -> int:
    """Return seconds to wait BEFORE the next send attempt.

    See module docstring for the schedule + rationale. Always returns
    a non-negative int — negative ``attempts`` is treated as 0.
    """
    if attempts < 0:
        attempts = 0
    return _BACKOFF_SECONDS[min(attempts, len(_BACKOFF_SECONDS) - 1)]


def schedule_total_seconds() -> int:
    """Sum of every wait the schedule will impose across max_attempts.
    Useful for ops dashboards (« worst-case time to dead »)."""
    return sum(_BACKOFF_SECONDS)
