"""Validate registry structure and evidence completeness."""

from __future__ import annotations

import argparse

from .registry import invalid_artifacts, load_registry, missing_artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)

    payload = load_registry()
    problems: list[str] = []
    counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
    for item in payload["experiments"]:
        counts[item["status"]] += 1
        missing = missing_artifacts(item)
        if item["status"] == "completed" and missing:
            problems.append(f"{item['id']}: completed but missing {missing}")
        if item["status"] == "completed":
            invalid = invalid_artifacts(item)
            if invalid:
                problems.append(f"{item['id']}: completed but invalid/empty {invalid}")
        if args.require_complete and item["status"] != "completed":
            problems.append(f"{item['id']}: status={item['status']}")
        if args.require_complete and missing:
            problems.append(f"{item['id']}: missing {missing}")

    print("registry counts:", counts)
    if problems:
        for problem in problems:
            print("FAIL:", problem)
        return 1
    print("experiment registry OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
