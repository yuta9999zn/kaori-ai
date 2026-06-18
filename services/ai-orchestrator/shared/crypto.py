"""
P2-S25 D3 — P2-ENC-001 field-level encryption utility.

AES-256-GCM authenticated encryption for column-level PII protection
(cccd / salary / contact details / contract numbers). Per-tenant key
loaded from Vault path (prod) or env var (dev) via the kaori_vault
helper.

Wire format
-----------
encrypt(plaintext, key) -> base64( version(1B) || IV(12B) || ciphertext+tag )
                                                                      ^^^
                                            GCM tag is appended by `Cipher`
                                            primitives — 16 bytes after the
                                            ciphertext body.

version byte = 1 today (single AES-256-GCM scheme). Future schemes
bump the version and decrypt() routes by leading byte.

K-rules
-------
K-5: this module is the data-layer side of PII redaction. Pair with
     redact_pii() at the LLM-call boundary. Encryption is at-rest;
     redaction is in-transit-to-external.
K-9: when encrypting NUMERIC(14,4) money fields, caller converts to
     str() first — encryption preserves the textual representation.
K-18: production key MUST live in Vault. Dev profile may read from
     KAORI_FIELD_KEY env var; the module logs a warning at boot if
     no Vault path is configured.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Optional

import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = structlog.get_logger()


_VERSION_V1 = 1                     # AES-256-GCM
_KEY_BYTES   = 32                   # 256 bits
_IV_BYTES    = 12                   # GCM-recommended nonce size


class CryptoError(Exception):
    """Raised on decrypt failure (bad tag, malformed ciphertext, etc.)."""


@dataclass(frozen=True)
class WrappedKey:
    """Container for a tenant key + the tenant_field_keys.version it
    came from. Returned by Vault resolver; consumed by encrypt/decrypt
    + the re-encrypt worker.

    .version is the TENANT key version (1, 2, 3, ... bumped per
    rotation). It is NOT the AES scheme version — that is a wire-format
    constant (_VERSION_V1) and stays the leading byte of every
    ciphertext regardless of which tenant key produced it.
    """
    key_bytes: bytes
    version:   int

    def __post_init__(self):
        if len(self.key_bytes) != _KEY_BYTES:
            raise ValueError(
                f"AES-256-GCM key must be {_KEY_BYTES} bytes; got {len(self.key_bytes)}"
            )
        if self.version < 1:
            raise ValueError(
                f"WrappedKey.version must be >= 1 (tenant key version); got {self.version}"
            )


def _aesgcm(key: bytes) -> AESGCM:
    if len(key) != _KEY_BYTES:
        raise ValueError(
            f"AES-256 key must be {_KEY_BYTES} bytes; got {len(key)}"
        )
    return AESGCM(key)


def _try_decrypt(ciphertext_b64: str, key: WrappedKey) -> Optional[str]:
    """Internal helper for history-fallback decrypt. Returns plaintext
    on success, None on ANY CryptoError (GCM tag mismatch, corrupt
    wire format, unsupported scheme version). The caller (worker /
    decrypt_field_with_history) is expected to try the next key when
    None is returned; only after ALL keys fail does the caller raise.
    """
    try:
        return decrypt_field(ciphertext_b64, key)
    except CryptoError:
        return None


def decrypt_field_with_history(
    ciphertext_b64: str,
    keys: list[WrappedKey],
) -> tuple[str, int]:
    """Decrypt by trying each candidate key in order, returning the
    plaintext + version of the key that worked.

    Caller supplies keys ordered by likelihood (typically: current
    version first, then history descending). Used by the re-encrypt
    worker (P2 retro item 6) and by any read path that must tolerate
    rows still under a previous key version after a rotation.

    Raises CryptoError if NO key in the list decrypts. The empty-string
    short-circuit from decrypt_field() still applies (returns "", -1
    to signal "no decryption attempted").
    """
    if ciphertext_b64 is None or ciphertext_b64 == "":
        return "", -1
    if not keys:
        raise CryptoError("decrypt_field_with_history: no candidate keys")

    for key in keys:
        pt = _try_decrypt(ciphertext_b64, key)
        if pt is not None:
            return pt, key.version
    raise CryptoError(
        f"All {len(keys)} candidate keys failed to decrypt ciphertext "
        f"(versions tried: {[k.version for k in keys]})"
    )


def encrypt_field(plaintext: str, key: WrappedKey) -> str:
    """Encrypt plaintext → base64 string suitable for TEXT column.

    Caller must hold the tenant's WrappedKey (resolved via Vault).
    Empty plaintext returns "" — null-friendly for NULLABLE columns.
    """
    if plaintext is None or plaintext == "":
        return ""
    aes = _aesgcm(key.key_bytes)
    iv = os.urandom(_IV_BYTES)
    ct = aes.encrypt(iv, plaintext.encode("utf-8"), associated_data=None)
    blob = bytes([_VERSION_V1]) + iv + ct
    return base64.b64encode(blob).decode("ascii")


def decrypt_field(ciphertext_b64: str, key: WrappedKey) -> str:
    """Decrypt base64 → plaintext. Raises CryptoError on tampering."""
    if ciphertext_b64 is None or ciphertext_b64 == "":
        return ""
    try:
        blob = base64.b64decode(ciphertext_b64)
    except Exception as e:  # noqa: BLE001
        raise CryptoError(f"base64 decode failed: {e}") from e
    if len(blob) < 1 + _IV_BYTES + 16:    # version + IV + min tag size
        raise CryptoError("ciphertext too short")
    version = blob[0]
    if version != _VERSION_V1:
        raise CryptoError(
            f"Unsupported ciphertext version {version}; expected {_VERSION_V1}"
        )
    iv = blob[1:1 + _IV_BYTES]
    ct = blob[1 + _IV_BYTES:]
    aes = _aesgcm(key.key_bytes)
    try:
        pt = aes.decrypt(iv, ct, associated_data=None)
    except Exception as e:  # noqa: BLE001
        raise CryptoError(f"GCM decrypt failed (tampering or wrong key): {e}") from e
    return pt.decode("utf-8")


# ─── Key resolver — Vault prod / env dev ─────────────────────────────


def _is_production() -> bool:
    return os.getenv("KAORI_PROFILE", "dev") in ("production", "prod")


def resolve_tenant_key(
    *,
    tenant_id: str,
    key_ref: str,
    version: int = 1,
    vault_client: Optional[object] = None,
    dev_inline_key_env: str = "KAORI_FIELD_KEY",
) -> WrappedKey:
    """Resolve a tenant's field-encryption key. K-18 — production MUST
    resolve via Vault; dev profile falls back to inline:/env var.

    Three key_ref formats:
      - "vault:<path>"     — read from Vault at <path>; expects {"key": "<b64>"}
      - "inline:<b64>"     — literal dev key (DEV ONLY — refused in prod)
      - "" (or env var)    — KAORI_FIELD_KEY env var (DEV ONLY — refused in prod)

    `version` is the TENANT key version (from tenant_field_keys.version
    or tenant_field_key_versions.version). Returned WrappedKey carries
    it through to encrypt_field/decrypt_field.

    Custom `vault_client` may be injected for tests; defaults to the
    process-global KaoriVault singleton. Pass a non-None vault_client
    even when key_ref starts with `vault:` only when you need test
    isolation — production uses the global.
    """
    is_prod = _is_production()

    # ---- Vault path ----
    if key_ref and key_ref.startswith("vault:"):
        path = key_ref[len("vault:"):]
        client = vault_client
        if client is None:
            try:
                from .kaori_vault import get_default_client
                client = get_default_client()
            except Exception as e:   # noqa: BLE001
                raise CryptoError(
                    f"K-18: vault: ref requires kaori_vault module; import "
                    f"failed: {e}"
                ) from e
        try:
            # KaoriVault.read_sync returns the data dict {"key": "..."} or
            # for back-compat injected mocks may return raw base64 string.
            raw = client.read_sync(path) if hasattr(client, "read_sync") \
                else client.read(path)
        except Exception as e:   # noqa: BLE001
            log.error("crypto.vault_resolve_failed",
                      tenant_id=tenant_id, key_ref=key_ref, error=str(e))
            raise
        if isinstance(raw, dict):
            if "key" not in raw:
                raise CryptoError(
                    f"Vault path '{path}' missing required 'key' field; "
                    f"got keys {sorted(raw.keys())}"
                )
            key_b64 = raw["key"]
        else:
            key_b64 = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        return WrappedKey(
            key_bytes=base64.b64decode(key_b64),
            version=version,
        )

    # ---- Legacy custom vault_client path (kept for test compat) ----
    if vault_client is not None and (not key_ref or not key_ref.startswith(("inline:", "vault:"))):
        try:
            raw = vault_client.read(key_ref)
            if not raw:
                raise ValueError(f"Vault returned empty key at {key_ref}")
            key_b64 = raw if isinstance(raw, str) else raw.decode("utf-8")
            return WrappedKey(
                key_bytes=base64.b64decode(key_b64),
                version=version,
            )
        except Exception as e:   # noqa: BLE001
            log.error("crypto.vault_resolve_failed",
                      tenant_id=tenant_id, key_ref=key_ref, error=str(e))
            raise

    # ---- Dev fallbacks (refused under KAORI_PROFILE=production) ----
    if is_prod:
        raise CryptoError(
            f"K-18: production profile requires key_ref starting with "
            f"'vault:' for tenant {tenant_id}; got "
            f"{'<empty>' if not key_ref else key_ref[:20] + '...'}"
        )

    if key_ref and key_ref.startswith("inline:"):
        key_b64 = key_ref[len("inline:"):]
        log.warning("crypto.using_inline_key",
                    tenant_id=tenant_id,
                    note="inline key is DEV-ONLY; provision Vault for prod")
        return WrappedKey(
            key_bytes=base64.b64decode(key_b64),
            version=version,
        )
    env_val = os.getenv(dev_inline_key_env)
    if env_val:
        log.warning("crypto.using_env_key",
                    tenant_id=tenant_id,
                    env_var=dev_inline_key_env,
                    note="env-var key is DEV-ONLY; provision Vault for prod")
        return WrappedKey(
            key_bytes=base64.b64decode(env_val),
            version=version,
        )
    raise CryptoError(
        f"No key source available for tenant {tenant_id}: "
        f"no Vault path, no inline: prefix, no {dev_inline_key_env} env var."
    )


def generate_key_b64() -> str:
    """Generate a fresh AES-256 key as base64 string. Use during
    tenant onboarding to write into tenant_field_keys.key_ref (dev)
    or as the value pushed to Vault (prod)."""
    return base64.b64encode(os.urandom(_KEY_BYTES)).decode("ascii")
