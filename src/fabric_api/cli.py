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
    result: Iterable[dict[str, Any]]
    match args.command:
        case "workspaces":
            result = FabricClient(credential, args.fabric_url).workspaces()
        case "capacities":
            result = FabricClient(credential, args.fabric_url).capacities()
        case "domains":
            result = FabricClient(credential, args.fabric_url).domains()
        case "deployment-pipelines":
            result = FabricClient(credential, args.fabric_url).deployment_pipelines()
        case "items":
            result = FabricClient(credential, args.fabric_url).items(
                args.workspace_id, args.item_type
            )
        case "pipeline-runs":
            result = FabricClient(credential, args.fabric_url).pipeline_runs(
                args.workspace_id, args.pipeline_id
            )
        case "gateways":
            result = PowerBIClient(credential, args.powerbi_url).gateways()
        case "data-sources":
            result = PowerBIClient(credential, args.powerbi_url).data_sources(args.gateway_id)
        case "activity-events":
            result = PowerBIClient(credential, args.powerbi_url).activity_events(
                args.start, args.end
            )
        case _:
            raise AssertionError("unreachable")
    print(json.dumps(list(result), indent=2))


if __name__ == "__main__":
    main()
