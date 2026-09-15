"""Export all accessible Fabric workspaces and their items to one JSON file."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from azure.core.exceptions import AzureError

from fabric_api import ApiError, FabricClient, PowerBIClient, TokenCredentialFactory


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


def collect_activity_events(
    client: PowerBIClient,
    *,
    start: datetime,
    end: datetime,
    workspace_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Collect tenant activity events and optionally retain selected workspaces."""
    events = client.list_activity_events(start, end)
    if workspace_ids is not None:
        events = [
            event
            for event in events
            if str(event.get("WorkspaceId", event.get("workspaceId", ""))) in workspace_ids
        ]
    return {
        "startDateTime": start.isoformat(),
        "endDateTime": end.isoformat(),
        "events": events,
    }


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
        "--activity-start",
        type=_parse_datetime,
        help="Include tenant audit events starting at this ISO 8601 UTC timestamp.",
    )
    parser.add_argument(
        "--activity-end",
        type=_parse_datetime,
        help="Include tenant audit events ending at this ISO 8601 UTC timestamp.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("fabric-workspace-inventory.json"),
        help="Output JSON path (default: fabric-workspace-inventory.json).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if bool(args.activity_start) != bool(args.activity_end):
        parser.error("--activity-start and --activity-end must be provided together")

    credential = TokenCredentialFactory.from_environment().create()
    workspace_ids = set(args.workspace_ids) if args.workspace_ids else None
    with FabricClient(credential, timeout=30, max_retries=2) as client:
        inventory = collect_inventory(
            client,
            workspace_ids=workspace_ids,
            include_platform_resources=args.include_platform_resources,
        )
    if args.activity_start and args.activity_end:
        try:
            with PowerBIClient(credential, timeout=30, max_retries=2) as client:
                inventory["activityEvents"] = collect_activity_events(
                    client,
                    start=args.activity_start,
                    end=args.activity_end,
                    workspace_ids=workspace_ids,
                )
        except (ApiError, AzureError) as error:
            inventory["activityEvents"] = {
                "startDateTime": args.activity_start.isoformat(),
                "endDateTime": args.activity_end.isoformat(),
                "events": [],
                "error": str(error),
            }
            inventory["errors"].append(
                {
                    "scope": "activityEvents",
                    "error": str(error),
                }
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


def _parse_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "expected an ISO 8601 timestamp with an offset, for example 2026-09-14T00:00:00Z"
        ) from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a UTC offset")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
