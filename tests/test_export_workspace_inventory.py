from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from examples.export_workspace_inventory import (
    build_parser,
    collect_activity_events,
    collect_inventory,
)
from fabric_api.models import FabricItem


class FakeFabricClient:
    def list_workspaces(self) -> list[Mapping[str, Any]]:
        return [
            {
                "id": "workspace-one",
                "displayName": "Finance",
                "type": "Workspace",
                "capacityId": "capacity-one",
                "capacityRegion": "East US",
            },
            {
                "id": "workspace-two",
                "displayName": "Sales",
                "type": "Workspace",
            },
        ]

    def list_items(self, workspace_id: str) -> list[FabricItem]:
        return [
            FabricItem.from_dict(
                {
                    "id": f"{workspace_id}-item",
                    "displayName": "Inventory",
                    "type": "Lakehouse",
                    "workspaceId": workspace_id,
                    "description": "Full inventory data",
                    "customProperty": "preserved",
                }
            )
        ]


class FakePowerBIClient:
    def list_activity_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[Mapping[str, Any]]:
        return [
            {"Id": "one", "WorkspaceId": "workspace-one", "Activity": "ViewReport"},
            {"Id": "two", "WorkspaceId": "workspace-two", "Activity": "RefreshDataset"},
            {"Id": "three", "Activity": "GetSnapshots"},
        ]


def test_collect_inventory_preserves_raw_payloads_and_flattened_rows() -> None:
    inventory = collect_inventory(FakeFabricClient())  # type: ignore[arg-type]

    assert len(inventory["workspaces"]) == 2
    assert len(inventory["rows"]) == 2
    assert inventory["rows"][0]["workspaceName"] == "Finance"
    assert inventory["rows"][0]["capacityId"] == "capacity-one"
    assert inventory["rows"][0]["itemType"] == "Lakehouse"
    assert inventory["rows"][0]["item"]["customProperty"] == "preserved"


def test_collect_inventory_can_limit_workspaces() -> None:
    inventory = collect_inventory(
        FakeFabricClient(),  # type: ignore[arg-type]
        workspace_ids={"workspace-two"},
    )

    assert [entry["workspace"]["id"] for entry in inventory["workspaces"]] == ["workspace-two"]


def test_collect_activity_events_can_filter_selected_workspaces() -> None:
    start = datetime(2026, 9, 14, tzinfo=timezone.utc)
    end = datetime(2026, 9, 14, 23, 59, 59, tzinfo=timezone.utc)

    result = collect_activity_events(
        FakePowerBIClient(),  # type: ignore[arg-type]
        start=start,
        end=end,
        workspace_ids={"workspace-two"},
    )

    assert [event["Id"] for event in result["events"]] == ["two"]


def test_activity_timestamp_arguments_parse_utc_values() -> None:
    args = build_parser().parse_args(
        [
            "--activity-start",
            "2026-09-14T00:00:00Z",
            "--activity-end",
            "2026-09-14T23:59:59Z",
        ]
    )

    assert args.activity_start.tzinfo is not None
    assert args.activity_end.tzinfo is not None
