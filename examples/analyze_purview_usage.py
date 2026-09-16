"""Export Copilot or Power BI/Fabric usage summaries from Purview Audit."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from fabric_api.cli import main as fabric_api_main


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("copilot", "powerbi"))
    args, remaining = parser.parse_known_args(argv)
    command = "copilot-usage" if args.mode == "copilot" else "powerbi-usage"
    return fabric_api_main([command, *remaining])


if __name__ == "__main__":
    raise SystemExit(main())
