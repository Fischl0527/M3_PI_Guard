"""Write a reproducible package snapshot for an isolated experiment runtime."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_snapshot(packages: list[str]) -> dict[str, object]:
    selected: dict[str, str | None] = {}
    for package in packages:
        try:
            selected[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            selected[package] = None
    installed = sorted(
        (
            {"name": dist.metadata.get("Name", ""), "version": dist.version}
            for dist in importlib.metadata.distributions()
        ),
        key=lambda row: (str(row["name"]).casefold(), str(row["version"])),
    )
    return {
        "schema": "m3-python-environment-snapshot-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(selected.values()) else "incomplete",
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "selected_packages": selected,
        "environment_paths": {
            "HF_HOME": os.environ.get("HF_HOME"),
            "HF_HUB_CACHE": os.environ.get("HF_HUB_CACHE"),
            "PIP_CACHE_DIR": os.environ.get("PIP_CACHE_DIR"),
        },
        "installed_distributions": installed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_snapshot(args.package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
