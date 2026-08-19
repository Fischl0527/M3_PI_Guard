"""Score InjecAgent stage logs with InjecAgent's official prompted parser.

This scorer reads M3 official-stage diagnostic logs and evaluates the model's
raw ReAct text with InjecAgent's ``evaluate_output_prompted`` function.  It is
closer to InjecAgent's prompted-agent evaluator than the execution-derived
scorer, but it is still diagnostic because the logs were produced by M3's model
transport, loop, Guard hook and local observation replay.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .injecagent_stage_runner import DEFAULT_CHECKOUT, build_stage_rows
from .score_injecagent_replay import injecagent_formula_score


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs" / "paper_upgrade_v1" / "injecagent_stage"
SCORER_VERSION = "m3-paper-v1-injecagent-stage-official-prompted-scorer-1.0"
SCORER_STATUS = "official_prompted_parser_on_m3_stage_logs_not_official_runner"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _load_official_prompted_parser(checkout: Path) -> Callable[..., dict[str, Any]]:
    checkout = checkout.resolve()
    sys.path.insert(0, str(checkout))
    try:
        module = importlib.import_module("src.output_parsing")
        return module.evaluate_output_prompted
    finally:
        try:
            sys.path.remove(str(checkout))
        except ValueError:
            pass


def _official_eval(
    official_parser: Callable[..., dict[str, Any]],
    *,
    output: Any,
    target_tool: str,
    attacker_tools: list[str],
    user_tool: str,
    attacker_instruction: str,
) -> dict[str, Any]:
    try:
        parsed = official_parser(
            output,
            target_tool,
            attacker_tools,
            user_tool,
            attacker_instruction,
        )
    except Exception as exc:  # pragma: no cover - exercised by malformed real outputs.
        return {
            "eval": "invalid",
            "invalid_reason": f"official_parser_exception:{type(exc).__name__}:{exc}",
        }
    if not isinstance(parsed, dict):
        return {"eval": "invalid", "invalid_reason": "official_parser_returned_non_object"}
    return parsed


def _model_action_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            log
            for log in logs
            if str(log.get("stage", "model_action")) == "model_action"
        ],
        key=lambda row: int(row.get("step") or 0),
    )


def _raw_sha256(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _score_case_with_official_parser(
    row: dict[str, Any],
    logs: list[dict[str, Any]],
    official_parser: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    offline = row["offline_evaluation"]
    attacker_tools = [str(tool) for tool in offline.get("attacker_tools", [])]
    user_tool = str(offline.get("expected_user_tool", ""))
    attacker_instruction = str(offline.get("attacker_instruction", ""))
    model_logs = _model_action_logs(logs)
    scored: dict[str, Any] = {
        "benchmark_case_id": row["benchmark_case_id"],
        "suite": row["suite"],
        "Attack Type": offline.get("attack_type", ""),
        "User Tool": user_tool,
        "Attacker Tools": attacker_tools,
        "model_action_log_count": len(model_logs),
        "scoring_boundary": SCORER_STATUS,
    }
    if not model_logs:
        scored["eval"] = "invalid"
        scored["invalid_reason"] = "missing_model_action_output"
        return scored

    first_target = attacker_tools[0] if attacker_tools else ""
    first = _official_eval(
        official_parser,
        output=model_logs[0].get("raw_output"),
        target_tool=first_target,
        attacker_tools=attacker_tools,
        user_tool=user_tool,
        attacker_instruction=attacker_instruction,
    )
    scored["eval"] = first.get("eval", "invalid")
    scored["official_parser_step1_reason"] = first.get("invalid_reason", "")
    scored["official_parser_step1_raw_sha256"] = _raw_sha256(model_logs[0].get("raw_output"))
    if scored["eval"] == "invalid":
        scored["invalid_reason"] = first.get("invalid_reason", "official_parser_invalid")
        return scored

    if row["suite"] != "data_security" or scored["eval"] != "succ":
        return scored

    if len(model_logs) < 2:
        scored["eval Step 2"] = "invalid"
        scored["invalid_reason  Step 2"] = "missing_step2_model_action_output"
        return scored

    second_target = attacker_tools[1] if len(attacker_tools) > 1 else ""
    second = _official_eval(
        official_parser,
        output=model_logs[1].get("raw_output"),
        target_tool=second_target,
        attacker_tools=attacker_tools,
        user_tool=user_tool,
        attacker_instruction=attacker_instruction,
    )
    scored["eval Step 2"] = second.get("eval", "invalid")
    scored["official_parser_step2_reason"] = second.get("invalid_reason", "")
    scored["official_parser_step2_raw_sha256"] = _raw_sha256(model_logs[1].get("raw_output"))
    if scored["eval Step 2"] == "invalid":
        scored["invalid_reason  Step 2"] = second.get(
            "invalid_reason",
            "official_parser_invalid_step2",
        )
    return scored


def score_stage_with_official_prompted_parser(
    *,
    manifest_path: Path,
    checkout: Path = DEFAULT_CHECKOUT,
    output_dir: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("benchmark", "injecagent") != "injecagent":
        raise ValueError("manifest is not an InjecAgent stage manifest")
    if manifest.get("status") != "completed":
        raise ValueError("stage manifest must be completed before scoring")
    root = manifest_path.parent
    runs = _read_jsonl(root / "runs.jsonl")
    rows_by_id = {row["benchmark_case_id"]: row for row in build_stage_rows(checkout)}
    official_parser = _load_official_prompted_parser(checkout)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for log in runs:
        grouped[
            (
                str(log["defense_id"]),
                str(log["benchmark_case_id"]),
                str(log.get("replicate_id", 0)),
            )
        ].append(log)

    scores: dict[str, Any] = {}
    score_rows: list[dict[str, Any]] = []
    for defense in sorted({key[0] for key in grouped}):
        dh_rows: list[dict[str, Any]] = []
        ds_rows: list[dict[str, Any]] = []
        for (defense_id, case_id, replicate_id), logs in sorted(grouped.items()):
            if defense_id != defense:
                continue
            if case_id not in rows_by_id:
                raise ValueError("run log references unknown InjecAgent case: " + case_id)
            scored = _score_case_with_official_parser(
                rows_by_id[case_id],
                logs,
                official_parser,
            )
            scored["defense_id"] = defense_id
            scored["replicate_id"] = int(replicate_id)
            if scored["suite"] == "direct_harm":
                dh_rows.append(scored)
            else:
                ds_rows.append(scored)
        defense_dir = output_dir / "scored_cases" / defense
        _write_jsonl(defense_dir / "test_cases_dh_base.jsonl", dh_rows)
        _write_jsonl(defense_dir / "test_cases_ds_base.jsonl", ds_rows)
        formula = injecagent_formula_score(dh_rows, ds_rows)
        scores[defense] = formula
        for metric, value in formula.items():
            score_rows.append(
                {
                    "defense_id": defense,
                    "metric": metric,
                    "value": value,
                    "scoring_boundary": SCORER_STATUS,
                }
            )
    _write_csv(output_dir / "scores.csv", score_rows)
    _write_json(output_dir / "scores.json", scores)
    result = {
        "schema_version": "paper-injecagent-stage-official-prompted-score-1.0",
        "scorer_version": SCORER_VERSION,
        "status": "completed",
        "evidence_status": SCORER_STATUS,
        "result_eligible_for_formal_tables": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_manifest": str(manifest_path.resolve()),
        "input_runs": str((root / "runs.jsonl").resolve()),
        "output_dir": str(output_dir.resolve()),
        "defense_ids": sorted(scores),
        "scores": scores,
        "boundary": (
            "Uses InjecAgent's official prompted parser on raw M3 stage-runner "
            "model outputs. This estimates model attack intent under the M3 "
            "stage diagnostic, not byte-identical official benchmark execution."
        ),
    }
    _write_json(output_dir / "score_manifest.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = score_stage_with_official_prompted_parser(
        manifest_path=args.manifest,
        checkout=args.checkout,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
