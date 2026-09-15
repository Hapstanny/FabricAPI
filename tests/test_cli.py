from __future__ import annotations

import sys

import pytest

from fabric_api import cli


class Client:
    def __init__(self, *args: object) -> None:
        pass

    def items(self, workspace_id: str, item_type: str | None) -> list[dict[str, str]]:
        assert (workspace_id, item_type) == ("workspace", None)
        return [{"id": "item"}]


def test_items_dispatch_without_type(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "credential_from_environment", lambda interactive: object())
    monkeypatch.setattr(cli, "FabricClient", Client)
    monkeypatch.setattr(cli, "PowerBIClient", Client)
    monkeypatch.setattr(sys, "argv", ["fabric-api", "items", "workspace"])

    cli.main()

    assert capsys.readouterr().out == '[\n  {\n    "id": "item"\n  }\n]\n'
