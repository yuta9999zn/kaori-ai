"""
P2-AUTH-001 SSO provider adapters.

OAuth 2.0 Authorization Code Flow (with PKCE-ready interfaces; v0
ships without PKCE since both Google + Microsoft accept client_secret
on the token-exchange leg).

Exports
-------
SSOProvider        — abstract base; one subclass per provider
GoogleProvider     — Gmail / Workspace
MicrosoftProvider  — Entra ID multi-tenant (activated when anh có
                      Microsoft tenant credentials)
get_provider(name) — factory; returns the singleton instance for
                      'google' | 'microsoft', or raises UnknownProvider
"""
from .base import (
    OAuthExchangeError,
    ProviderNotConfigured,
    SSOProfile,
    SSOProvider,
    UnknownProvider,
)
from .google import GoogleProvider
from .microsoft import MicrosoftProvider


_REGISTRY: dict[str, SSOProvider] = {}


def get_provider(name: str) -> SSOProvider:
    """Return the registered provider instance. Caches per process.

    Reads provider config (client_id, client_secret, redirect_uri) from
    env vars at first call. Raises UnknownProvider for unsupported
    names.
    """
    key = name.strip().lower()
    if key in _REGISTRY:
        return _REGISTRY[key]
    if key == "google":
        _REGISTRY[key] = GoogleProvider.from_env()
    elif key == "microsoft":
        _REGISTRY[key] = MicrosoftProvider.from_env()
    else:
        raise UnknownProvider(f"Unknown SSO provider: {name!r}")
    return _REGISTRY[key]


def _reset_registry_for_tests() -> None:
    _REGISTRY.clear()


__all__ = [
    "SSOProvider",
    "SSOProfile",
    "OAuthExchangeError",
    "ProviderNotConfigured",
    "UnknownProvider",
    "GoogleProvider",
    "MicrosoftProvider",
    "get_provider",
    "_reset_registry_for_tests",
]
