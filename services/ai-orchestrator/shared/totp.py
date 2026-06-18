"""
P2-S25 D2 — RFC 6238 TOTP (HMAC-SHA1, 30s step, 6 digits).

Pure-Python implementation; no pyotp dependency. Mirrors auth-service
TotpService.java wire shape so cross-service token verification works
identically.

Wire format for storage
-----------------------
secret_enc = base64( IV(12B) || AES-256-GCM-ciphertext(secret_bytes(20B)) )

The AES-GCM encryption lives in shared/crypto.py with a different
header (1-byte version + IV + ciphertext). For MFA secrets we use a
SIMPLER header (just IV + ciphertext) to match auth-service's
TotpService — cross-service compatibility wins over header consistency.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from typing import Optional
from urllib.parse import quote

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_TOTP_DIGITS  = 6
_TOTP_PERIOD  = 30          # seconds
_SECRET_BYTES = 20          # 160 bits — standard for SHA-1 HMAC
_IV_BYTES     = 12          # GCM recommendation


# ─── Secret generation + encryption at rest ─────────────────────────


def generate_secret() -> bytes:
    """Cryptographically-random 20-byte secret."""
    return secrets.token_bytes(_SECRET_BYTES)


def encrypt_secret(secret: bytes, master_key: bytes) -> str:
    """Encrypt a TOTP secret with the platform master key (KAORI_MFA_KEY
    today; Vault-issued per-tenant key in Phase 2+).

    Wire: base64(IV(12B) || GCM-ciphertext(secret)). Matches auth-service
    TotpService.encrypt() byte-for-byte so cross-verify works.
    """
    if len(master_key) != 32:
        raise ValueError("master_key must be 32 bytes (AES-256)")
    aes = AESGCM(master_key)
    iv = os.urandom(_IV_BYTES)
    ct = aes.encrypt(iv, secret, associated_data=None)
    return base64.b64encode(iv + ct).decode("ascii")


def decrypt_secret(secret_enc_b64: str, master_key: bytes) -> bytes:
    """Reverse of encrypt_secret."""
    if len(master_key) != 32:
        raise ValueError("master_key must be 32 bytes (AES-256)")
    blob = base64.b64decode(secret_enc_b64)
    if len(blob) < _IV_BYTES + 16:
        raise ValueError("ciphertext too short")
    iv = blob[:_IV_BYTES]
    ct = blob[_IV_BYTES:]
    aes = AESGCM(master_key)
    return aes.decrypt(iv, ct, associated_data=None)


# ─── TOTP code computation ───────────────────────────────────────────


def _hotp(secret: bytes, counter: int, digits: int = _TOTP_DIGITS) -> str:
    """RFC 4226 HOTP — HMAC-SHA1 + dynamic truncation."""
    msg = struct.pack(">Q", counter)
    h = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (
        ((h[offset]     & 0x7F) << 24)
        | ((h[offset + 1] & 0xFF) << 16)
        | ((h[offset + 2] & 0xFF) << 8)
        |  (h[offset + 3] & 0xFF)
    )
    return str(code % (10 ** digits)).zfill(digits)


def totp_code(
    secret: bytes,
    *,
    at: Optional[int] = None,
    digits: int = _TOTP_DIGITS,
    period: int = _TOTP_PERIOD,
) -> str:
    """Generate the TOTP code for the given moment (default: now).

    `at` = unix epoch seconds. Useful for tests + drift-window verify.
    """
    if at is None:
        at = int(time.time())
    counter = at // period
    return _hotp(secret, counter, digits=digits)


def verify_totp(
    secret: bytes,
    code: str,
    *,
    at: Optional[int] = None,
    drift_steps: int = 1,
) -> bool:
    """Verify code against the current 30s step ± drift_steps neighbours.

    drift_steps=1 (default) → accept ±30s clock skew. Set to 0 for
    strict matching (e.g. one-time recovery scenarios).
    """
    if not code or not code.isdigit() or len(code) != _TOTP_DIGITS:
        return False
    if at is None:
        at = int(time.time())
    base_counter = at // _TOTP_PERIOD
    for offset in range(-drift_steps, drift_steps + 1):
        candidate = _hotp(secret, base_counter + offset)
        # Constant-time compare resists timing oracle attacks
        if hmac.compare_digest(candidate, code):
            return True
    return False


# ─── otpauth:// URI for QR code generation ──────────────────────────


def base32_encode(secret: bytes) -> str:
    """Standard base32 for Google Authenticator manual entry. Strips
    the padding '=' that GA's input field rejects."""
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def otpauth_url(
    *,
    issuer: str,
    account_label: str,
    secret: bytes,
    digits: int = _TOTP_DIGITS,
    period: int = _TOTP_PERIOD,
) -> str:
    """Build otpauth://totp/<issuer>:<label>?secret=<b32>&issuer=<i>&...

    `issuer` is the brand shown in the authenticator app; per-tenant
    suffix is recommended (e.g. 'Kaori AI - Vingroup').
    """
    secret_b32 = base32_encode(secret)
    label = f"{issuer}:{account_label}"
    return (
        f"otpauth://totp/{quote(label)}"
        f"?secret={secret_b32}"
        f"&issuer={quote(issuer)}"
        f"&algorithm=SHA1"
        f"&digits={digits}"
        f"&period={period}"
    )


# ─── Backup codes ────────────────────────────────────────────────────


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate `count` recovery codes. Each is 10 chars (uppercase
    alphanumeric, easy to read on paper). Caller hashes via SHA-256
    before storing."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # avoid 0/O/1/I
    return [
        "".join(secrets.choice(alphabet) for _ in range(10))
        for _ in range(count)
    ]


def hash_backup_code(code: str) -> str:
    """SHA-256 hash of a backup code (hex string). Match by hashing the
    user-entered code and comparing against stored hash."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
