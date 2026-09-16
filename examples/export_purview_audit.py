"""Export Microsoft Purview audit records through Microsoft Graph v1.0."""

from __future__ import annotations

import sys

from fabric_api.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["purview-audit", "export", *sys.argv[1:]]))
