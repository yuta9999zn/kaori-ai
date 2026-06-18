"""
P2-AUTH-001 SSO base class — defines the contract every concrete
provider implements.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


class UnknownProvider(ValueError):
    """Raised when a request names an SSO provider that isn't registered."""


class OAuthExchangeError(RuntimeError):
    """Raised on any failure in the OAuth code → access_token exchange
    (network, 4xx from provider, invalid response shape)."""


class ProviderNotConfigured(RuntimeError):
    """Raised when a provider's env-var credentials are missing.
    Caller (router) should surface as 503 with a clear message so
    SSO buttons in the FE can be hidden for providers not yet set up.
    """


@dataclass(frozen=True)
class SSOProfile:
    """Normalized user profile after callback. All concrete providers
    map their raw response into this shape."""
    provider:        str       # 'google' | 'microsoft'
    provider_sub:    str       # stable per-provider identifier
    email:           str       # verified email
    email_verified:  bool
    name:            Optional[str]
    raw_profile:     dict[str, Any]


class SSOProvider(ABC):
    """One subclass per OAuth provider."""

    name: str = ""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id     = client_id
        self.client_secret = client_secret
        self.redirect_uri  = redirect_uri

    @abstractmethod
    def authorize_url(self, *, state: str) -> str:
        """Build the URL to redirect the user to for authorization."""

    @abstractmethod
    async def exchange_code_for_profile(self, *, code: str) -> SSOProfile:
        """Exchange the authorization code for tokens, then call the
        userinfo endpoint and return a normalized SSOProfile.

        Raises OAuthExchangeError on any provider-side failure.
        """
