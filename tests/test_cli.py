from __future__ import annotations

import pytest

from fabric_api.cli import ITEM_COMMANDS, build_parser, main


def test_item_shortcuts_are_registered() -> None:
    parser = build_parser()

    for command in ITEM_COMMANDS:
        args = parser.parse_args([command, "workspace-id"])
        assert args.command == command
        assert args.workspace_id == "workspace-id"


def test_generic_items_accepts_unknown_future_type() -> None:
    args = build_parser().parse_args(["items", "workspace-id", "--type", "FutureItem"])

    assert args.item_type == "FutureItem"


def test_auth_configuration_error_is_reported_as_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("FABRIC_AUTH_MODE", "client_secret")
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)

    assert main(["workspaces"]) == 1
    assert '"error"' in capsys.readouterr().out
