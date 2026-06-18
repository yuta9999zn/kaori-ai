"""
kaori_vault — thin async wrapper over HashiCorp Vault KV v2 secrets engine.

P1-S2 (K-18 prep) — sets up the contract surface so services can adopt
Vault-backed secrets incrementally. Phase 1 calls KEEP using env vars;
Phase 1.5+ migration ports each secret to a Vault path defined here.

Path conventions (ADR-0013, K-1 spirit applied to Vault):

    secret/data/platform/<bucket>/<key>           # platform-scoped
    secret/data/tenant/<tenant_id>/<bucket>/<key> # tenant-scoped
    secret/data/service/<service_name>/<key>      # service-scoped

Where ``<bucket>`` is one of:
    api_keys         — outbound API keys (vendor LLM, Stripe, SMTP)
    oauth_tokens     — refresh tokens (per tenant after first OAuth)
    db_credentials   — DSN for tenant-isolated databases (Phase 2)
    connectors       — Misa / Fast / Zalo Business creds per tenant

Production (P15-S9): switch from VAULT_TOKEN root auth to AppRole +
KMS unseal. The wrapper API surface stays identical.
"""
from __future__ import annotations

import os
from typing import Any, Optional
from uuid import UUID

import httpx
import structlog

log = structlog.get_logger()

DEFAULT_VAULT_ADDR = "http://vault:8200"
DEFAULT_KV_MOUNT = "secret"  # KV v2 default mount point


class VaultError(RuntimeError):
    """Raised on any Vault operation failure (network, auth, missing path).

    Callers should catch this and either fail loud (mandatory secret
    paths like LLM API keys) or fall back to env vars (Phase 1
    transition path). Never silently default to empty string — that
    masks misconfiguration as runtime bugs.
    """


class KaoriVault:
    """Async client for Vault KV v2 secrets.

    Single instance per service process. Token + base URL come from
    environment so dev/staging/prod swap without code changes.

    Methods:
        get(path)                  — read a secret (returns dict or raises)
        put(path, data)            — write/overwrite a secret
        delete(path)               — soft-delete latest version
        tenant_path(tenant_id, ..) — build canonical tenant secret path
        platform_path(bucket, key) — build canonical platform secret path

    Phase 1 transition: a service can call ``get(path)`` and on
    VaultError fall back to ``os.getenv(...)``. Phase 1.5+ removes the
    fallback once all secrets are in Vault.
    """

    def __init__(
        self,
        addr: Optional[str] = None,
        token: Optional[str] = None,
        kv_mount: str = DEFAULT_KV_MOUNT,
        timeout: float = 5.0,
    ) -> None:
        self.addr = (addr or os.getenv("VAULT_ADDR", DEFAULT_VAULT_ADDR)).rstrip("/")
        self.token = token or os.getenv("VAULT_TOKEN", "")
        self.kv_mount = kv_mount
        self.timeout = timeout

        if not self.token:
            log.warning(
                "kaori_vault.no_token",
                msg="VAULT_TOKEN not set — get/put will fail. OK during Phase 1 if env-var fallback is in place.",
            )

    # ------------------------------------------------------------------
    # Path builders — single source of truth so callers don't hand-roll
    # ------------------------------------------------------------------

    @staticmethod
    def platform_path(bucket: str, key: str) -> str:
        """Build ``platform/<bucket>/<key>`` — for global Kaori secrets
        (vendor LLM keys, SMTP creds, infra DB roots)."""
        return f"platform/{bucket}/{key}"

    @staticmethod
    def tenant_path(tenant_id: str | UUID, bucket: str, key: str) -> str:
        """Build ``tenant/<id>/<bucket>/<key>`` — for per-tenant secrets
        (OAuth refresh tokens, connector credentials).

        UUIDs are stringified; non-UUID tenant identifiers are passed
        through verbatim so workspace_id-style paths (Phase 1 legacy)
        work too.
        """
        if isinstance(tenant_id, UUID):
            tenant_id = str(tenant_id)
        return f"tenant/{tenant_id}/{bucket}/{key}"

    @staticmethod
    def service_path(service_name: str, key: str) -> str:
        """Build ``service/<name>/<key>`` — for service-internal secrets
        (signing keys, encryption-at-rest keys)."""
        return f"service/{service_name}/{key}"

    # ------------------------------------------------------------------
    # KV v2 operations
    # ------------------------------------------------------------------

    def read_sync(self, path: str) -> dict[str, Any]:
        """Synchronous KV v2 read for callers that can't await.

        Used by shared/crypto.py (field-key resolver — called from sync
        helper paths that the worker invokes from inside async DB calls,
        but the worker itself doesn't want to plumb async through every
        rule). Same network shape as async get() — separate httpx
        Client so the two paths don't share connection pools.
        """
        url = f"{self.addr}/v1/{self.kv_mount}/data/{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._auth_headers())
        except httpx.HTTPError as exc:
            raise VaultError(f"Vault network error reading {path}: {exc}") from exc

        if resp.status_code == 404:
            raise VaultError(f"Vault path not found: {path}")
        if resp.status_code == 403:
            raise VaultError(f"Vault forbidden for {path} (token lacks read capability)")
        if resp.status_code != 200:
            raise VaultError(
                f"Vault unexpected status {resp.status_code} reading {path}: {resp.text[:200]}"
            )
        body = resp.json()
        try:
            return body["data"]["data"]
        except (KeyError, TypeError) as exc:
            raise VaultError(f"Vault response shape unexpected for {path}: {exc}") from exc

    def write_sync(self, path: str, data: dict[str, Any]) -> None:
        """Synchronous KV v2 write — used by field-key rotation to
        store a freshly-generated tenant key under a Vault path."""
        url = f"{self.addr}/v1/{self.kv_mount}/data/{path}"
        payload = {"data": data}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self._auth_headers(), json=payload)
        except httpx.HTTPError as exc:
            raise VaultError(f"Vault network error writing {path}: {exc}") from exc
        if resp.status_code not in (200, 204):
            raise VaultError(
                f"Vault write {path} failed status {resp.status_code}: {resp.text[:200]}"
            )

    async def get(self, path: str) -> dict[str, Any]:
        """Read latest version of a KV v2 secret.

        Returns the data dict (the values, not the metadata wrapper).
        Raises VaultError if path missing, token invalid, or network
        unreachable. Caller decides whether to fall back to env.
        """
        url = f"{self.addr}/v1/{self.kv_mount}/data/{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self._auth_headers())
        except httpx.HTTPError as exc:
            raise VaultError(f"Vault network error reading {path}: {exc}") from exc

        if resp.status_code == 404:
            raise VaultError(f"Vault path not found: {path}")
        if resp.status_code == 403:
            raise VaultError(f"Vault forbidden for {path} (token lacks read capability)")
        if resp.status_code != 200:
            raise VaultError(
                f"Vault unexpected status {resp.status_code} reading {path}: {resp.text[:200]}"
            )

        body = resp.json()
        # KV v2 wraps data: { "data": { "data": {...}, "metadata": {...} } }
        try:
            return body["data"]["data"]
        except (KeyError, TypeError) as exc:
            raise VaultError(f"Vault response shape unexpected for {path}: {exc}") from exc

    async def put(self, path: str, data: dict[str, Any]) -> None:
        """Write (or overwrite) a KV v2 secret.

        Vault auto-versions; the caller doesn't manage CAS unless they
        want optimistic concurrency. Phase 1 we don't.
        """
        url = f"{self.addr}/v1/{self.kv_mount}/data/{path}"
        payload = {"data": data}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=self._auth_headers(), json=payload)
        except httpx.HTTPError as exc:
            raise VaultError(f"Vault network error writing {path}: {exc}") from exc

        if resp.status_code not in (200, 204):
            raise VaultError(
                f"Vault write {path} failed status {resp.status_code}: {resp.text[:200]}"
            )

    async def delete(self, path: str) -> None:
        """Soft-delete latest version (KV v2 keeps history; full purge
        requires a separate destroy call we deliberately don't expose
        here — accidental destroys are unrecoverable)."""
        url = f"{self.addr}/v1/{self.kv_mount}/data/{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.delete(url, headers=self._auth_headers())
        except httpx.HTTPError as exc:
            raise VaultError(f"Vault network error deleting {path}: {exc}") from exc

        if resp.status_code not in (200, 204, 404):
            raise VaultError(
                f"Vault delete {path} failed status {resp.status_code}: {resp.text[:200]}"
            )

    # ------------------------------------------------------------------
    # K-18 transition helper
    # ------------------------------------------------------------------

    async def get_or_env(
        self,
        env_var: str,
        vault_path: str,
        *,
        key: Optional[str] = None,
        profile: Optional[str] = None,
    ) -> str:
        """Resolve a secret via Vault first, env-var fallback for
        non-production profiles. K-18 enforcement.

        Resolution chain:
          1. Read `vault_path`; on success return data[key] (or the
             single value if `key` not given).
          2. On VaultError when `profile != "production"`: fall back
             to os.getenv(env_var) and log a warning.
          3. On VaultError when `profile == "production"`: re-raise.
             Production MUST resolve via Vault per K-18.

        `profile` defaults to env var KAORI_PROFILE (dev / staging /
        production). Bare absence → "dev".

        Use cases:
          - llm-gateway resolving Anthropic API key during the Phase 1
            → Phase 1.5+ transition, before the env var is retired.
          - notification-service resolving SMTP creds.
          - auth-service resolving the MFA master key (Phase 1.5
            migration target per CLAUDE.md §15).
        """
        profile = profile or os.getenv("KAORI_PROFILE", "dev")
        is_production = profile in ("production", "prod")

        try:
            data = await self.get(vault_path)
        except VaultError as exc:
            if is_production:
                raise VaultError(
                    f"K-18: production requires Vault '{vault_path}' to resolve; "
                    f"env-var fallback to '{env_var}' is disabled. Original: {exc}"
                ) from exc
            env_val = os.getenv(env_var)
            if env_val is None:
                raise VaultError(
                    f"Vault '{vault_path}' missing AND env var '{env_var}' unset. "
                    f"Set one to proceed. Vault error: {exc}"
                ) from exc
            log.warning(
                "kaori_vault.env_fallback",
                vault_path=vault_path,
                env_var=env_var,
                profile=profile,
                msg="Vault unreachable; using env-var fallback. Migrate to Vault before production.",
            )
            return env_val

        if key is not None:
            if key not in data:
                raise VaultError(
                    f"Vault '{vault_path}' returned data without expected key '{key}'. "
                    f"Available keys: {sorted(data.keys())}"
                )
            return str(data[key])
        # No key requested — collapse single-value secrets to the lone value.
        if len(data) == 1:
            return str(next(iter(data.values())))
        raise VaultError(
            f"Vault '{vault_path}' has {len(data)} keys; pass `key=` to disambiguate. "
            f"Available: {sorted(data.keys())}"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        if not self.token:
            raise VaultError(
                "VAULT_TOKEN not configured — set env var or pass token explicitly."
            )
        return {"X-Vault-Token": self.token}


# ---------------------------------------------------------------------------
# Convenience: process-global lazy singleton.
# Most services need exactly one Vault client; build on first call.
# ---------------------------------------------------------------------------

_default_client: KaoriVault | None = None


def get_default_client() -> KaoriVault:
    """Return the lazily-initialised process-global client.

    Tests should construct their own ``KaoriVault(...)`` instance and
    inject it rather than relying on this global; the global exists so
    application code can write ``vault = get_default_client()`` without
    a constructor dance.
    """
    global _default_client
    if _default_client is None:
        _default_client = KaoriVault()
    return _default_client
