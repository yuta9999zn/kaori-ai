"""
Canonical field validators — executable mirror of ``docs/specs/VALIDATION_RULES.md``.

VALIDATION_RULES.md declares itself the *single canonical source* of input
validation and states that drift "surfaces when CI snapshot test diffs FE
form-validator output vs BE Pydantic field_validator against fixture inputs."
That CI test (and a centralised validator on either side) never existed —
validation lived scattered inline across routers and FE template components,
so the promised guarantee was unenforced.

This module makes the spec **executable**: one function per field type from
§2 of the spec, each returning a :class:`ValidationResult` carrying the exact
``USR-ERR*`` code the spec's "Error" column dictates. The companion test
``tests/test_validation_rules_parity.py`` runs the shared fixture set
(``tests/fixtures/validation_rules_fixtures.json``) through these functions —
that is the BE half of the parity check. When the FE restructure resumes
(CLAUDE.md §2), the FE validator consumes the *same* fixtures, closing the
loop the spec described.

Error codes are the FE-facing ``USR-ERR*`` from ``docs/specs/MESSAGE_DEFINITIONS.md``
(the spec's own "Error" column). For RFC 7807 emission, map them to the
machine ``VALIDATION.*`` codes via :data:`USR_TO_VALIDATION_CODE`
(see ``shared/error_codes.py``).

Scope: deterministic field-shape rules (type / length / charset / structure /
numeric range). Business rules that need a DB round-trip — uniqueness
(``USR-ERR6``) — are NOT decided here; the validator returns ``ok`` for shape
and the caller enforces uniqueness against the tenant. Each such gap is noted
inline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import error_codes

# --- spec "Error" column codes (docs/specs/MESSAGE_DEFINITIONS.md §2) ---------
USR_ERR_REQUIRED = "USR-ERR3"   # required field missing
USR_ERR_FORMAT = "USR-ERR4"     # invalid format / charset / structure
USR_ERR_LENGTH = "USR-ERR5"     # length out of [min, max]
USR_ERR_DUPLICATE = "USR-ERR6"  # business: unique-in-tenant — caller enforces
USR_ERR_RANGE = "USR-ERR7"      # value out of allowed numeric range

# Map FE-facing USR-ERR* → machine VALIDATION.* for RFC 7807 ``code`` field.
USR_TO_VALIDATION_CODE = {
    USR_ERR_REQUIRED: error_codes.VALIDATION_MISSING_FIELD,
    USR_ERR_FORMAT: error_codes.VALIDATION_GENERIC,
    USR_ERR_LENGTH: error_codes.VALIDATION_GENERIC,
    USR_ERR_DUPLICATE: "RESOURCE.CONFLICT",
    USR_ERR_RANGE: error_codes.VALIDATION_GENERIC,
}


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of one field validation.

    ``ok`` True → value passes the spec's shape rules. On failure ``errcode``
    is one of the ``USR-ERR*`` constants and ``reason`` is a short
    machine-readable tag (not user-facing — the FE i18n catalog maps
    ``errcode`` → display string).
    """

    ok: bool
    errcode: str | None = None
    reason: str | None = None

    @classmethod
    def passed(cls) -> "ValidationResult":
        return cls(ok=True)

    @classmethod
    def fail(cls, errcode: str, reason: str) -> "ValidationResult":
        return cls(ok=False, errcode=errcode, reason=reason)


# Control chars + emoji + the XSS/script markers the spec bans across text fields.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_EMOJI_RE = re.compile(
    "[" "\U0001f300-\U0001faff" "\U00002600-\U000027bf" "\U0001f000-\U0001f0ff" "]",
    flags=re.UNICODE,
)
_XSS_RE = re.compile(r"<\s*script|<\s*/\s*script|javascript:|onerror\s*=|<\s*img", re.I)
_SQLI_RE = re.compile(r"(--|;|/\*|\*/|\bunion\b\s+\bselect\b|\bdrop\b\s+\btable\b)", re.I)


def _has_banned_text(value: str) -> bool:
    return bool(_CONTROL_RE.search(value) or _EMOJI_RE.search(value) or _XSS_RE.search(value))


# =====================================================================
# 2.1 Email
# =====================================================================
_EMAIL_LOCAL_CHARS = re.compile(r"^[A-Za-z0-9._+\-]+$")
_EMAIL_SPECIALS = set("._+-")
_DOMAIN_LABEL = re.compile(r"^[A-Za-z0-9\-]{1,63}$")
_TLD = re.compile(r"^[A-Za-z]{2,6}$")


def validate_email(value: str) -> ValidationResult:
    """§2.1 — length 6-255, ``local@domain`` structure, charset + structural rules."""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if " " in value:
        return ValidationResult.fail(USR_ERR_FORMAT, "whitespace")
    if not (6 <= len(value) <= 255):
        return ValidationResult.fail(USR_ERR_LENGTH, "length")
    if value.count("@") != 1:
        return ValidationResult.fail(USR_ERR_FORMAT, "at_count")
    local, domain = value.split("@", 1)
    if not local or not _EMAIL_LOCAL_CHARS.match(local):
        return ValidationResult.fail(USR_ERR_FORMAT, "local_charset")
    if local[0] in _EMAIL_SPECIALS or local[-1] in _EMAIL_SPECIALS:
        return ValidationResult.fail(USR_ERR_FORMAT, "local_edge_special")
    if any(a in _EMAIL_SPECIALS and b in _EMAIL_SPECIALS for a, b in zip(local, local[1:])):
        return ValidationResult.fail(USR_ERR_FORMAT, "local_double_special")
    if local.isdigit() or all(c in _EMAIL_SPECIALS for c in local):
        return ValidationResult.fail(USR_ERR_FORMAT, "local_all_digit_or_special")
    labels = domain.split(".")
    if len(labels) < 2:
        return ValidationResult.fail(USR_ERR_FORMAT, "domain_labels")
    for label in labels[:-1]:
        if not _DOMAIN_LABEL.match(label) or label.isdigit() or set(label) == {"-"}:
            return ValidationResult.fail(USR_ERR_FORMAT, "domain_label")
    if not _TLD.match(labels[-1]):
        return ValidationResult.fail(USR_ERR_FORMAT, "tld")
    return ValidationResult.passed()


# =====================================================================
# 2.2 Username / Code
# =====================================================================
# Latin + Vietnamese base letters WITHOUT tone marks (spec: A-Y/a-y "không dấu").
_USERNAME_CHARS = re.compile(r"^[A-Za-z0-9._+\-]+$")
_USERNAME_SPECIALS = set("._+-")


def validate_username(value: str) -> ValidationResult:
    """§2.2 — length 1-20, no diacritics/emoji, charset, not all-special."""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    value = value.strip()
    if not (1 <= len(value) <= 20):
        return ValidationResult.fail(USR_ERR_LENGTH, "length")
    if _EMOJI_RE.search(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "emoji")
    if not _USERNAME_CHARS.match(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "charset")
    if all(c in _USERNAME_SPECIALS for c in value):
        return ValidationResult.fail(USR_ERR_FORMAT, "all_special")
    return ValidationResult.passed()


# =====================================================================
# 2.3 Password
# =====================================================================
_PASSWORD_ALLOWED = re.compile(r"^[A-Za-z0-9.\-_+*&@(),;:?!/']+$")


def validate_password(value: str, *, min_len: int = 8, max_len: int = 64) -> ValidationResult:
    """§2.3 — length per-field (default 8-64), charset, no control/emoji/script/SQLi."""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if not (min_len <= len(value) <= max_len):
        return ValidationResult.fail(USR_ERR_LENGTH, "length")
    if _CONTROL_RE.search(value) or _EMOJI_RE.search(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "control_or_emoji")
    if _XSS_RE.search(value) or _SQLI_RE.search(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "injection")
    if not _PASSWORD_ALLOWED.match(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "charset")
    return ValidationResult.passed()


# =====================================================================
# 2.4 Number — natural int
# =====================================================================
def validate_natural_int(value: str | int) -> ValidationResult:
    """§2.4 — digits only, convertible to int, ``>= 0``."""
    s = str(value)
    if s == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if not s.isdigit():  # str.isdigit rejects '-', '.', spaces, signs
        return ValidationResult.fail(USR_ERR_FORMAT, "non_digit")
    return ValidationResult.passed()  # isdigit() already implies >= 0


# =====================================================================
# 2.5 Free text / description
# =====================================================================
def validate_free_text(value: str, *, min_len: int = 1, max_len: int = 2000) -> ValidationResult:
    """§2.5 — length 1-2000, no emoji/script/XSS. (Whitelist HTML tags are
    declared per-field by the caller; this base validator rejects all tags.)"""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if not (min_len <= len(value) <= max_len):
        return ValidationResult.fail(USR_ERR_LENGTH, "length")
    if _EMOJI_RE.search(value) or _XSS_RE.search(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "emoji_or_xss")
    return ValidationResult.passed()


# =====================================================================
# 2.6 Datetime — dd/mm/yyyy hh:mm:ss
# =====================================================================
_DATETIME_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})$")
_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def validate_datetime(value: str) -> ValidationResult:
    """§2.6 — format ``dd/mm/yyyy hh:mm:ss``, real calendar date, year 1900-2200."""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    m = _DATETIME_RE.match(value)
    if not m:
        return ValidationResult.fail(USR_ERR_FORMAT, "format")
    dd, mm, yyyy, hh, mi, ss = (int(g) for g in m.groups())
    if not (1900 <= yyyy <= 2200) or not (1 <= mm <= 12):
        return ValidationResult.fail(USR_ERR_FORMAT, "range")
    max_day = 29 if (mm == 2 and _is_leap(yyyy)) else _DAYS_IN_MONTH[mm - 1]
    if not (1 <= dd <= max_day):
        return ValidationResult.fail(USR_ERR_FORMAT, "day")
    if hh > 23 or mi > 59 or ss > 59:
        return ValidationResult.fail(USR_ERR_FORMAT, "time")
    return ValidationResult.passed()


# =====================================================================
# 2.7 Year — yyyy, 1900-2200
# =====================================================================
def validate_year(value: str | int) -> ValidationResult:
    """§2.7 — length 4-5, digits only, structure yyyy, range 1900-2200."""
    s = str(value).strip()
    if s == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if not (4 <= len(s) <= 5):
        return ValidationResult.fail(USR_ERR_LENGTH, "length")
    if not s.isdigit():
        return ValidationResult.fail(USR_ERR_FORMAT, "non_digit")
    if not (1900 <= int(s) <= 2200):
        return ValidationResult.fail(USR_ERR_RANGE, "range")
    return ValidationResult.passed()


# =====================================================================
# 2.8 Phone — VN 8/10/11 digits, or E.164 intl <= 15
# =====================================================================
_PHONE_RE = re.compile(r"^\+?[0-9]+$")


def validate_phone(value: str) -> ValidationResult:
    """§2.8 — chars ``0-9`` and a single leading ``+``; VN lengths 8/10/11
    (excl. ``+``), international E.164 max 15 digits."""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if not _PHONE_RE.match(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "charset")
    intl = value.startswith("+")
    digits = value[1:] if intl else value
    if not digits.isdigit():
        return ValidationResult.fail(USR_ERR_FORMAT, "charset")
    n = len(digits)
    if intl:
        if not (1 <= n <= 15):
            return ValidationResult.fail(USR_ERR_FORMAT, "e164_length")
    else:
        if n not in (8, 10, 11):
            return ValidationResult.fail(USR_ERR_FORMAT, "vn_length")
    return ValidationResult.passed()


# =====================================================================
# 2.9 URL  (spec typo "USER-ERR*" normalised to USR-ERR* here)
# =====================================================================
_URL_RE = re.compile(r"^https?://([A-Za-z0-9\-]{1,63})(\.[A-Za-z0-9\-]{1,63})+(/[^\s]*)?$")


def validate_url(value: str) -> ValidationResult:
    """§2.9 — http(s):// scheme, host with >=1 dot, total <= 255, label <= 63,
    no script/malware. (Spec's ``USER-ERR*`` typo maps to ``USR-ERR*``.)"""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if len(value) > 255:
        return ValidationResult.fail(USR_ERR_LENGTH, "length")
    if _XSS_RE.search(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "xss")
    if not _URL_RE.match(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "structure")
    return ValidationResult.passed()


# =====================================================================
# 2.10 Symbol / doc_no
# =====================================================================
# A-Z, Vietnamese uppercase Ă Â Ê Đ Ô Ơ Ư, digits, ':' '/' '-'.
_DOCNO_RE = re.compile(r"^[A-ZĂÂÊĐÔƠƯ0-9:/\-]+$")


def validate_doc_no(value: str) -> ValidationResult:
    """§2.10 — max 50, charset (auto-uppercase), structure ``Số/KýhiệuVB``."""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    value = value.strip().upper()  # spec: auto-uppercase if lowercase
    if len(value) > 50:
        return ValidationResult.fail(USR_ERR_LENGTH, "length")
    if " " in value:
        return ValidationResult.fail(USR_ERR_FORMAT, "whitespace")
    if not _DOCNO_RE.match(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "charset")
    return ValidationResult.passed()


# =====================================================================
# 2.11 Address
# =====================================================================
_ADDRESS_RE = re.compile(r"^[\wÀ-ỹ0-9 ,\.\-/]+$", re.UNICODE)


def validate_address(value: str) -> ValidationResult:
    """§2.11 — length 10-255, charset (letters/digits/space/``,.-/``).
    Structural format (3 variants) and uniqueness (``USR-ERR6``) are
    business rules the caller layers on top."""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if not (10 <= len(value) <= 255):
        return ValidationResult.fail(USR_ERR_LENGTH, "length")
    if _EMOJI_RE.search(value) or not _ADDRESS_RE.match(value):
        return ValidationResult.fail(USR_ERR_FORMAT, "charset")
    return ValidationResult.passed()


# =====================================================================
# 2.12 National ID (CCCD)
# =====================================================================
def validate_national_id(value: str, *, foreign: bool = False) -> ValidationResult:
    """§2.12 — VN: 9 or 12 digits; Foreign: <= 20, ``[0-9a-z]``, not all-letters."""
    if value is None or value == "":
        return ValidationResult.fail(USR_ERR_REQUIRED, "empty")
    if foreign:
        if len(value) > 20:
            return ValidationResult.fail(USR_ERR_LENGTH, "length")
        if not re.match(r"^[0-9a-z]+$", value):
            return ValidationResult.fail(USR_ERR_FORMAT, "charset")
        if value.isalpha():
            return ValidationResult.fail(USR_ERR_FORMAT, "all_letters")
        return ValidationResult.passed()
    if not value.isdigit():
        return ValidationResult.fail(USR_ERR_FORMAT, "non_digit")
    if len(value) not in (9, 12):
        return ValidationResult.fail(USR_ERR_LENGTH, "vn_length")
    return ValidationResult.passed()


# Registry: field-type name → validator. Keys MUST match the fixture JSON.
VALIDATORS = {
    "email": validate_email,
    "username": validate_username,
    "password": validate_password,
    "natural_int": validate_natural_int,
    "free_text": validate_free_text,
    "datetime": validate_datetime,
    "year": validate_year,
    "phone": validate_phone,
    "url": validate_url,
    "doc_no": validate_doc_no,
    "address": validate_address,
    "national_id": validate_national_id,
}
