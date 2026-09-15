"""Export all accessible Fabric workspaces and their items to one JSON file."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fabric_api import ApiError, FabricClient, TokenCredentialFactory


def collect_inventory(
    client: FabricClient,
    *,
    workspace_ids: set[str] | None = None,
    include_platform_resources: bool = False,
) -> dict[str, Any]:
    """Collect full workspace/item payloads and a flattened item inventory."""
    workspaces = client.list_workspaces()
    selected = [
        workspace
        for workspace in workspaces
        if workspace_ids is None or str(workspace.get("id")) in workspace_ids
    ]

    workspace_inventory: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for workspace in selected:
        workspace_id = str(workspace["id"])
        try:
            items = client.list_items(workspace_id)
        except ApiError as error:
            errors.append(
                {
                    "workspaceId": workspace_id,
                    "workspaceName": str(workspace.get("displayName", "")),
                    "error": str(error),
                }
            )
            workspace_inventory.append({"workspace": dict(workspace), "items": []})
            continue

        workspace_inventory.append(
            {
                "workspace": dict(workspace),
                "items": [dict(item.raw) for item in items],
            }
        )
        rows.extend(_flatten_items(workspace, items))

    result: dict[str, Any] = {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "workspaces": workspace_inventory,
        "rows": rows,
        "errors": errors,
    }
    if include_platform_resources:
        result["platformResources"] = _collect_platform_resources(client)
    return result


def _flatten_items(
    workspace: Mapping[str, Any],
    items: Sequence[Any],
) -> list[dict[str, Any]]:
    return [
        {
            "workspaceId": workspace["id"],
            "workspaceName": workspace.get("displayName"),
            "workspaceType": workspace.get("type"),
            "capacityId": workspace.get("capacityId"),
            "capacityRegion": workspace.get("capacityRegion"),
            "itemId": item.id,
            "itemName": item.display_name,
            "itemType": item.type,
            "itemDescription": item.description,
            "item": dict(item.raw),
        }
        for item in items
    ]


def _collect_platform_resources(client: FabricClient) -> dict[str, object]:
    resources: dict[str, object] = {}
    operations = {
        "capacities": client.list_capacities,
        "domains": client.list_domains,
        "deploymentPipelines": client.list_deployment_pipelines,
    }
    for name, operation in operations.items():
        try:
            resources[name] = operation()
        except ApiError as error:
            resources[name] = {"error": str(error)}
    return resources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export accessible Fabric workspaces and all their items to JSON."
    )
    parser.add_argument(
        "--workspace-id",
        action="append",
        dest="workspace_ids",
        help="Limit the export to this workspace ID. Repeat for multiple workspaces.",
    )
    parser.add_argument(
        "--include-platform-resources",
        action="store_true",
        help="Also request capacities, domains, and deployment pipelines.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("fabric-workspace-inventory.json"),
        help="Output JSON path (default: fabric-workspace-inventory.json).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    credential = TokenCredentialFactory.from_environment().create()
    with FabricClient(credential, timeout=30, max_retries=2) as client:
        inventory = collect_inventory(
            client,
            workspace_ids=set(args.workspace_ids) if args.workspace_ids else None,
            include_platform_resources=args.include_platform_resources,
        )

    args.output.write_text(
        json.dumps(inventory, indent=2, default=str),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(inventory['workspaces'])} workspaces and "
        f"{len(inventory['rows'])} items to {args.output}"
    )
    if inventory["errors"]:
        print(f"Completed with {len(inventory['errors'])} workspace errors.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
