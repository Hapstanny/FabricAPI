from __future__ import annotations

import pytest

from fabric_api.auth import TokenCredentialFactory
from fabric_api.errors import AuthenticationConfigurationError


def test_rejects_unknown_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FABRIC_AUTH_MODE", "unknown")

    with pytest.raises(AuthenticationConfigurationError, match="FABRIC_AUTH_MODE"):
        TokenCredentialFactory.from_environment()


def test_client_secret_requires_all_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FABRIC_AUTH_MODE", "client_secret")
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)

    with pytest.raises(AuthenticationConfigurationError, match="AZURE_TENANT_ID"):
        TokenCredentialFactory.from_environment().create()
