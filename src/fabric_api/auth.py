"""Azure Identity credential construction without handling secrets directly."""

from __future__ import annotations

import os

from azure.core.credentials import TokenCredential
from azure.identity import (
    ClientSecretCredential,
    DefaultAzureCredential,
    InteractiveBrowserCredential,
)


def credential_from_environment(interactive: bool = False) -> TokenCredential:
    """Use a service principal only when its complete configuration is present."""
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    if tenant_id and client_id and client_secret:
        return ClientSecretCredential(
            tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
        )
    if interactive:
        return InteractiveBrowserCredential()
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)
