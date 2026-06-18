"""
Tests for K-5 PII redaction (services/llm-gateway/pii.py).

Invariant K-5: prompts crossing the public-internet boundary (external
LLM providers) must have email / VN phone / CCCD-CMND identifiers
masked. The function is intentionally conservative — it would rather
over-mask a numeric column than leak a citizen-id to a third-party API.

These tests pin down the patterns ported from the original
ai-orchestrator/engine/llm_router.py so a future refactor can't
silently weaken them. Idempotency is checked because PII redaction is
applied per-message in the chat path (so the same payload may pass
through twice on a retry).
"""
from llm_gateway.pii import redact


# ─── Email ────────────────────────────────────────────────────────────

def test_redacts_simple_email():
    assert redact("Liên hệ user@example.com nhé") == "Liên hệ [email] nhé"


def test_redacts_email_with_dots_and_plus_in_local():
    assert redact("anh.tuan+kaori@company.co") == "[email]"


def test_redacts_multiple_emails_in_one_string():
    out = redact("from a@b.io to c.d@e.vn")
    assert out == "from [email] to [email]"


def test_does_not_touch_text_without_email():
    assert redact("Báo cáo doanh thu Q1") == "Báo cáo doanh thu Q1"


# ─── Vietnamese phone numbers ─────────────────────────────────────────

def test_redacts_phone_with_zero_prefix():
    assert redact("Gọi 0987654321 trước 5h") == "Gọi [phone] trước 5h"


def test_redacts_phone_with_84_prefix():
    assert redact("84912345678 đang chờ") == "[phone] đang chờ"


def test_redacts_phone_with_plus_84_prefix():
    # The phone pattern starts with \b which sits *between* the literal
    # '+' and the leading digit, so the '+' stays. The number itself is
    # masked — we still satisfy K-5; the residual '+' leaks no PII.
    assert redact("+84912345678") == "+[phone]"


def test_landline_falls_through_to_id_number_pattern():
    # Mobile pattern requires the second digit to be 3-9, so a landline
    # like 02xxxxxxxx (second digit = 2) doesn't match [phone]. But its
    # 10-digit length lands inside the 9-12 [id_number] window and the
    # conservative-by-design CCCD pattern eats it. That's intentional:
    # better to over-mask a number than risk leaking a real ID.
    assert redact("ext 0212345678") == "ext [id_number]"


# ─── ID numbers (CCCD / CMND) ─────────────────────────────────────────

def test_redacts_9_digit_id():
    assert redact("CMND 123456789") == "CMND [id_number]"


def test_redacts_12_digit_cccd():
    assert redact("CCCD 012345678901") == "CCCD [id_number]"


def test_does_not_redact_8_digit_number():
    # Below the 9-digit floor — legitimately a date / order number.
    assert redact("Order 12345678") == "Order 12345678"


def test_does_not_redact_13_digit_number():
    # Above the 12-digit ceiling — not an identifier shape we mask.
    assert redact("Code 1234567890123") == "Code 1234567890123"


# ─── Idempotency ──────────────────────────────────────────────────────

def test_redact_twice_equals_redact_once():
    """Chat path may re-redact the same message on retry. Result must
    not double-mask (e.g. ``[[email]]``)."""
    text = "user@example.com phone 0987654321 id 123456789"
    once = redact(text)
    twice = redact(once)
    assert once == twice
    assert "[email]" in once
    assert "[phone]" in once
    assert "[id_number]" in once


# ─── Mixed / unicode ──────────────────────────────────────────────────

def test_mixed_pii_in_vietnamese_sentence():
    text = "Khách hàng Nguyễn Văn A — email a.nguyen@kaori.vn, di động 0912345678"
    out = redact(text)
    assert "a.nguyen@kaori.vn" not in out
    assert "0912345678" not in out
    assert "[email]" in out
    assert "[phone]" in out
    # Vietnamese diacritics survive untouched.
    assert "Nguyễn Văn A" in out


def test_empty_string_returns_empty():
    assert redact("") == ""


def test_whitespace_only_unchanged():
    assert redact("   \n\t  ") == "   \n\t  "
