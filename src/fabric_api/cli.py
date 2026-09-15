"""Command-line interface for the example clients."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any

from .auth import TokenCredentialFactory
from .client import FabricClient, PowerBIClient
from .errors import FabricApiError

ITEM_COMMANDS: Mapping[str, str] = {
    "lakehouses": "Lakehouse",
    "warehouses": "Warehouse",
    "semantic-models": "SemanticModel",
    "dataflows": "Dataflow",
    "eventhouses": "Eventhouse",
    "eventstreams": "Eventstream",
    "kql-databases": "KQLDatabase",
    "kql-querysets": "KQLQueryset",
    "environments": "Environment",
    "dashboards": "Dashboard",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fabric-api",
        description="Microsoft Fabric and Power BI REST API examples",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("workspaces", help="List accessible Fabric workspaces")

    items = subparsers.add_parser("items", help="List items in a Fabric workspace")
    items.add_argument("workspace_id")
    items.add_argument("--type", dest="item_type")
    items.add_argument("--root-folder-id")
    items.add_argument(
        "--direct-only",
        action="store_true",
        help="Set recursive=false when listing a folder or workspace",
    )

    item = subparsers.add_parser("item", help="Get one Fabric item")
    item.add_argument("workspace_id")
    item.add_argument("item_id")

    for command, item_type in ITEM_COMMANDS.items():
        item_parser = subparsers.add_parser(
            command,
            help=f"List {item_type} items in a Fabric workspace",
        )
        item_parser.add_argument("workspace_id")

    subparsers.add_parser("capacities", help="List Fabric capacities")
    subparsers.add_parser("deployment-pipelines", help="List Fabric deployment pipelines")
    subparsers.add_parser("domains", help="List Fabric domains")

    activity_runs = subparsers.add_parser(
        "activity-runs",
        help="Query activity runs for a Fabric data pipeline job",
    )
    activity_runs.add_argument("workspace_id")
    activity_runs.add_argument("job_instance_id")
    activity_runs.add_argument("--updated-after", required=True, type=_parse_datetime)
    activity_runs.add_argument("--updated-before", required=True, type=_parse_datetime)

    subparsers.add_parser("gateways", help="List Power BI gateways")

    datasources = subparsers.add_parser(
        "datasources",
        help="List Power BI data sources for a semantic model",
    )
    datasources.add_argument("workspace_id")
    datasources.add_argument("semantic_model_id")

    activity = subparsers.add_parser(
        "activity-events",
        help="Get Power BI tenant activity events (admin)",
    )
    activity.add_argument("--start", required=True, type=_parse_datetime)
    activity.add_argument("--end", required=True, type=_parse_datetime)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        credential = TokenCredentialFactory.from_environment().create()
        timeout = float(os.getenv("FABRIC_API_TIMEOUT_SECONDS", "30"))
        max_retries = int(os.getenv("FABRIC_API_MAX_RETRIES", "4"))
        result = _run(args, credential, timeout=timeout, max_retries=max_retries)
    except (FabricApiError, ValueError) as error:
        print(json.dumps({"error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


def _run(
    args: argparse.Namespace,
    credential: Any,
    *,
    timeout: float,
    max_retries: int,
) -> object:
    fabric_base = os.getenv("FABRIC_API_BASE_URL", "https://api.fabric.microsoft.com")
    power_bi_base = os.getenv("POWER_BI_API_BASE_URL", "https://api.powerbi.com")

    if args.command in {"gateways", "datasources", "activity-events"}:
        with PowerBIClient(
            credential,
            base_url=power_bi_base,
            timeout=timeout,
            max_retries=max_retries,
        ) as client:
            if args.command == "gateways":
                return client.list_gateways()
            if args.command == "datasources":
                return client.list_datasources(args.workspace_id, args.semantic_model_id)
            return client.list_activity_events(args.start, args.end)

    with FabricClient(
        credential,
        base_url=fabric_base,
        timeout=timeout,
        max_retries=max_retries,
    ) as client:
        if args.command == "workspaces":
            return client.list_workspaces()
        if args.command == "items":
            return [
                asdict(item)
                for item in client.list_items(
                    args.workspace_id,
                    item_type=args.item_type,
                    recursive=False if args.direct_only else None,
                    root_folder_id=args.root_folder_id,
                )
            ]
        if args.command == "item":
            return asdict(client.get_item(args.workspace_id, args.item_id))
        if args.command == "activity-runs":
            return client.query_pipeline_activity_runs(
                args.workspace_id,
                args.job_instance_id,
                last_updated_after=args.updated_after,
                last_updated_before=args.updated_before,
            )
        if args.command in ITEM_COMMANDS:
            return [
                asdict(item)
                for item in client.list_items(
                    args.workspace_id,
                    item_type=ITEM_COMMANDS[args.command],
                )
            ]
        operations: Mapping[str, Callable[[], list[Mapping[str, Any]]]] = {
            "capacities": client.list_capacities,
            "deployment-pipelines": client.list_deployment_pipelines,
            "domains": client.list_domains,
        }
        return operations[args.command]()


def _parse_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "expected an ISO 8601 timestamp with an offset, for example 2026-09-14T00:00:00Z"
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
