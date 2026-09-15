"""Microsoft Entra credential configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

from azure.core.credentials import TokenCredential
from azure.identity import (
    ClientSecretCredential,
    DefaultAzureCredential,
    InteractiveBrowserCredential,
)

from .errors import AuthenticationConfigurationError

AuthMode = Literal["default", "interactive", "client_secret"]


@dataclass(frozen=True, slots=True)
class TokenCredentialFactory:
    """Build Azure Identity credentials without storing secrets in code."""

    mode: AuthMode = "default"

    @classmethod
    def from_environment(cls) -> TokenCredentialFactory:
        raw_mode = os.getenv("FABRIC_AUTH_MODE", "default").strip().lower()
        if raw_mode not in {"default", "interactive", "client_secret"}:
            raise AuthenticationConfigurationError(
                "FABRIC_AUTH_MODE must be default, interactive, or client_secret"
            )
        return cls(mode=cast(AuthMode, raw_mode))

    def create(self) -> TokenCredential:
        if self.mode == "interactive":
            return InteractiveBrowserCredential(
                tenant_id=os.getenv("AZURE_TENANT_ID") or None,
                client_id=os.getenv("AZURE_CLIENT_ID") or None,
            )
        if self.mode == "client_secret":
            required = {
                name: os.getenv(name)
                for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise AuthenticationConfigurationError(
                    f"Missing environment variables for client_secret mode: {', '.join(missing)}"
                )
            return ClientSecretCredential(
                tenant_id=required["AZURE_TENANT_ID"] or "",
                client_id=required["AZURE_CLIENT_ID"] or "",
                client_secret=required["AZURE_CLIENT_SECRET"] or "",
            )
        return DefaultAzureCredential(exclude_interactive_browser_credential=False)
