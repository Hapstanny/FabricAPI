from __future__ import annotations

import pytest

from fabric_api.cli import FABRIC_COPILOT_ACTIVITIES, ITEM_COMMANDS, build_parser, main


def test_item_shortcuts_are_registered() -> None:
    parser = build_parser()

    for command in ITEM_COMMANDS:
        args = parser.parse_args([command, "workspace-id"])
        assert args.command == command
        assert args.workspace_id == "workspace-id"


def test_generic_items_accepts_unknown_future_type() -> None:
    args = build_parser().parse_args(["items", "workspace-id", "--type", "FutureItem"])

    assert args.item_type == "FutureItem"


def test_datamarts_shortcut_is_not_advertised() -> None:
    assert "datamarts" not in ITEM_COMMANDS


def test_activity_events_accept_fabric_copilot_preset_and_exact_filters() -> None:
    args = build_parser().parse_args(
        [
            "activity-events",
            "--start",
            "2026-09-15T00:00:00Z",
            "--end",
            "2026-09-15T23:59:59Z",
            "--fabric-copilot",
            "--activity",
            "ViewReport",
            "--user",
            "analyst@example.com",
        ]
    )

    assert args.fabric_copilot is True
    assert args.activity == ["ViewReport"]
    assert args.user == "analyst@example.com"
    assert "FabricCopilotSessionMessageSent" in FABRIC_COPILOT_ACTIVITIES


def test_purview_commands_parse_documented_filters() -> None:
    args = build_parser().parse_args(
        [
            "purview-audit",
            "export",
            "--start",
            "2026-09-01T00:00:00Z",
            "--end",
            "2026-09-02T00:00:00Z",
            "--output",
            "audit-output",
            "--record-type",
            "powerBIAudit",
            "--service",
            "PowerBI",
            "--operation",
            "CopilotInteraction",
            "--user",
            "analyst@example.com",
            "--ip-address",
            "192.0.2.1",
            "--object-id",
            "report-id",
            "--keyword",
            "governance",
        ]
    )

    assert args.command == "purview-audit"
    assert args.purview_command == "export"
    assert args.record_type == ["powerBIAudit"]
    assert args.operation == ["CopilotInteraction"]
    assert args.service == "PowerBI"


def test_governance_shortcuts_require_time_window_and_output() -> None:
    for command in ("copilot-usage", "powerbi-usage"):
        args = build_parser().parse_args(
            [
                command,
                "--start",
                "2026-09-01T00:00:00Z",
                "--end",
                "2026-09-02T00:00:00Z",
                "--output",
                "audit-output",
            ]
        )

        assert args.command == command
        assert args.output.name == "audit-output"


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
