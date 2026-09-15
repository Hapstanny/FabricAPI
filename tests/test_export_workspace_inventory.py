from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from examples.export_workspace_inventory import collect_inventory
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
