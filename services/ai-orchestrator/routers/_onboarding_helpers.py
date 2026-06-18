"""
Pure helpers for onboard-from-csv (Hướng A finisher).

Two functions live here so the endpoint stays readable AND so they can be
unit-tested without a Postgres or FastAPI fixture:

  * classify_dept_name(raw)         — Vietnamese-aware mapping from a CSV
                                      'department' string to one of the
                                      7 dept_type enum values seeded by
                                      mig 046.
  * generate_pending_password_hash()— random unusable BCrypt hash for a
                                      freshly-onboarded user. Spring
                                      Security's BCryptPasswordEncoder
                                      (strength 10) validates against it
                                      during the password reset flow.
                                      Mirrors WorkspaceMemberService.invite()
                                      in auth-service.

Hướng A scope (per docs/archive/sprint/resume-checklists/JUNE_2026_RESUME_CHECKLIST.md §4a):
- This module derives ONLY the (dept_type, seniority_level) → default_role
  mapping. Per-permission granularity, cross-branch scoping, time-bound
  roles, and delegation are Hướng B / Phase 2 work.
"""
from __future__ import annotations

import re
import secrets
import string
from typing import Optional

import bcrypt


# Ordered list of (regex, dept_type). More-specific patterns first so e.g.
# "Chăm sóc khách hàng" hits customer_service before sliding into custom.
# Patterns are Unicode-aware and accent-friendly — the source CSVs are
# written by HR in Vietnamese with full diacritics.
_DEPT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"chăm\s*sóc\s*khách|khách\s*hàng|hỗ\s*trợ|\bcsr\b|\bcs\b",
                re.IGNORECASE),                                   "customer_service"),
    (re.compile(r"\bmarketing\b|tiếp\s*thị|truyền\s*thông",
                re.IGNORECASE),                                   "marketing"),
    (re.compile(r"\bsales?\b|kinh\s*doanh|bán\s*hàng",
                re.IGNORECASE),                                   "sales"),
    (re.compile(r"\bwarehouse\b|kho\s*vận|\bkho\b|logistics|vận\s*chuyển",
                re.IGNORECASE),                                   "warehouse"),
    (re.compile(r"\bhr\b|nhân\s*sự|tuyển\s*dụng",
                re.IGNORECASE),                                   "hr"),
    (re.compile(r"\bfinance\b|tài\s*chính|kế\s*toán|accounting",
                re.IGNORECASE),                                   "finance"),
]


def classify_dept_name(raw: Optional[str]) -> str:
    """Map a free-text department name (Vietnamese or English) to the
    7-value dept_type enum.

    Returns 'custom' when nothing matches — the seed in mig 061 includes
    a VIEWER row for ('custom', seniority) at every seniority level, so
    onboarding never fails purely on the dept side. A custom-typed user
    can still be promoted explicitly by a MANAGER via the PATCH role
    endpoint."""
    if raw is None:
        return 'custom'
    s = raw.strip()
    if not s:
        return 'custom'
    for pat, kind in _DEPT_PATTERNS:
        if pat.search(s):
            return kind
    return 'custom'


def generate_pending_password_hash() -> str:
    """Random unusable BCrypt hash for a freshly onboarded user.

    The plaintext is thrown away — no one (not even the inviter) holds
    it. To log in the user must complete the password reset flow
    (auth-service WorkspaceMemberService handles the email + token
    plumbing today; ai-orchestrator just lands the row).

    Strength 10 matches Spring Security's default, so BCryptPasswordEncoder
    in the Java auth-service will verify any later-set password against
    our hash without re-hashing on cost mismatch."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    plaintext = ''.join(secrets.choice(alphabet) for _ in range(32))
    return bcrypt.hashpw(
        plaintext.encode('utf-8'),
        bcrypt.gensalt(rounds=10),
    ).decode('utf-8')
