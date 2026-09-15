"""Command-line examples for supported Fabric and Power BI endpoint families."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from typing import Any

from .auth import credential_from_environment
from .client import FabricClient, PowerBIClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--fabric-url", default="https://api.fabric.microsoft.com/v1")
    parser.add_argument("--powerbi-url", default="https://api.powerbi.com/v1.0/myorg")
    sub = parser.add_subparsers(dest="command", required=True)
    commands: dict[str, list[tuple[str, str | None]]] = {
        "workspaces": [],
        "capacities": [],
        "domains": [],
        "deployment-pipelines": [],
        "gateways": [],
        "items": [("workspace_id", None), ("item_type", "?")],
        "pipeline-runs": [("workspace_id", None), ("pipeline_id", None)],
        "data-sources": [("gateway_id", None)],
        "activity-events": [("start", None), ("end", None)],
    }
    for name, command_args in commands.items():
        command = sub.add_parser(name)
        for arg, nargs in command_args:
            command.add_argument(arg, nargs=nargs)
    args = parser.parse_args()
    credential = credential_from_environment(args.interactive)
    fabric, power_bi = (
        FabricClient(credential, args.fabric_url),
        PowerBIClient(credential, args.powerbi_url),
    )
    result: Iterable[dict[str, Any]]
    match args.command:
        case "workspaces":
            result = fabric.workspaces()
        case "capacities":
            result = fabric.capacities()
        case "domains":
            result = fabric.domains()
        case "deployment-pipelines":
            result = fabric.deployment_pipelines()
        case "items":
            result = fabric.items(args.workspace_id, args.item_type)
        case "pipeline-runs":
            result = fabric.pipeline_runs(args.workspace_id, args.pipeline_id)
        case "gateways":
            result = power_bi.gateways()
        case "data-sources":
            result = power_bi.data_sources(args.gateway_id)
        case "activity-events":
            result = power_bi.activity_events(args.start, args.end)
        case _:
            raise AssertionError("unreachable")
    print(json.dumps(list(result), indent=2))


if __name__ == "__main__":
    main()
