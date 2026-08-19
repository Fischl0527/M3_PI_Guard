"""Run the frozen PromptGuard detector-only universe with complete window logs."""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import rows_sha256, sha256_file, write_jsonl


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = ROOT / "protocols" / "paper_upgrade_v1" / "promptguard_detector_formal_freeze_v1.json"
DEFAULT_OUTPUT = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "promptguard_detector_formal_v1" / "run"
)
RUNNER_VERSION = "m3-paper-v1-promptguard-detector-formal-run-1.0"
SCHEMA_VERSION = "paper-promptguard-detector-formal-run-1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not an object")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def binary_label_mapping(id2label: Mapping[Any, Any] | None) -> dict[int, str]:
    normalized = {
        int(key): str(value).strip().upper()
        for key, value in (id2label or {}).items()
        if str(key).isdigit()
    }
    if normalized == {0: "BENIGN", 1: "MALICIOUS"}:
        return normalized
    if normalized == {0: "LABEL_0", 1: "LABEL_1"} or not normalized:
        return {0: "BENIGN", 1: "MALICIOUS"}
    raise ValueError(f"unsupported PromptGuard id2label mapping: {normalized}")


def tokenizer_windows(tokenizer: Any, text: str, *, max_length: int) -> list[dict[str, Any]]:
    """Tokenize once, split payload ids, then add exact tokenizer special tokens."""

    if max_length <= 0:
        raise ValueError("max_length must be positive")
    special_count = int(tokenizer.num_special_tokens_to_add(pair=False))
    payload_limit = max_length - special_count
    if payload_limit <= 0:
        raise ValueError("max_length leaves no payload tokens")
    payload_ids = list(tokenizer.encode(str(text), add_special_tokens=False))
    payload_chunks = [
        payload_ids[offset : offset + payload_limit]
        for offset in range(0, len(payload_ids), payload_limit)
    ] or [[]]
    windows: list[dict[str, Any]] = []
    for index, payload in enumerate(payload_chunks):
        input_ids = list(tokenizer.build_inputs_with_special_tokens(payload))
        if len(input_ids) > max_length:
            raise ValueError("tokenizer special-token construction exceeded max_length")
        windows.append(
            {
                "window_index": index,
                "payload_token_count": len(payload),
                "encoded_token_count": len(input_ids),
                "input_ids": input_ids,
                "attention_mask": [1] * len(input_ids),
            }
        )
    return windows


def _validate_snapshot(snapshot: Path, frozen_rows: Sequence[Mapping[str, Any]]) -> None:
    observed: list[dict[str, Any]] = []
    for row in frozen_rows:
        path = snapshot / str(row["relative_path"])
        if not path.is_file():
            raise FileNotFoundError(f"frozen model file missing: {path}")
        observed.append(
            {
                "relative_path": str(row["relative_path"]),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if list(frozen_rows) != observed:
        raise ValueError("PromptGuard snapshot file size/hash drift")


def validate_freeze(freeze_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    freeze = _read_json(freeze_path)
    if freeze.get("status") != "frozen_pre_run":
        raise ValueError("freeze status must be frozen_pre_run")
    inputs_meta = freeze.get("frozen_inputs", {})
    inputs_path = Path(str(inputs_meta.get("inputs_path", "")))
    if not inputs_path.is_file():
        raise FileNotFoundError("frozen detector input file is missing")
    if sha256_file(inputs_path) != inputs_meta.get("inputs_file_sha256"):
        raise ValueError("frozen detector input file hash drift")
    inputs = _read_jsonl(inputs_path)
    if rows_sha256(inputs) != inputs_meta.get("inputs_sha256"):
        raise ValueError("frozen detector input rows hash drift")
    if len(inputs) != int(freeze.get("summary", {}).get("case_count", -1)):
        raise ValueError("frozen detector input count drift")
    ids = [str(row.get("case_id", "")) for row in inputs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate frozen detector case id")

    current_source = Path(__file__).resolve()
    source_rows = freeze.get("code_artifacts", [])
    current_expected = next(
        (
            row
            for row in source_rows
            if Path(str(row.get("path", ""))).resolve() == current_source
        ),
        None,
    )
    if not current_expected or current_expected.get("sha256") != sha256_file(current_source):
        raise ValueError("formal inference runner source differs from pre-run freeze")
    protocol = freeze.get("protocol", {})
    protocol_path = Path(str(protocol.get("path", "")))
    if not protocol_path.is_file() or sha256_file(protocol_path) != protocol.get("sha256"):
        raise ValueError("formal PromptGuard protocol hash drift")

    model = freeze.get("model", {})
    snapshot = Path(str(model.get("snapshot_path", "")))
    if snapshot.name != str(model.get("revision", "")):
        raise ValueError("model revision and snapshot directory disagree")
    _validate_snapshot(snapshot, model.get("snapshot_files", []))
    return freeze, inputs


def _existing_predictions(
    path: Path,
    *,
    freeze_sha256: str,
    inputs_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path):
        case_id = str(row.get("case_id", ""))
        if case_id in result:
            raise ValueError(f"duplicate resumed prediction: {case_id}")
        source = inputs_by_id.get(case_id)
        if source is None:
            raise ValueError(f"resumed prediction is outside freeze: {case_id}")
        if row.get("freeze_sha256") != freeze_sha256:
            raise ValueError(f"resumed prediction freeze mismatch: {case_id}")
        if row.get("scan_text_sha256") != source.get("scan_text_sha256"):
            raise ValueError(f"resumed prediction input mismatch: {case_id}")
        result[case_id] = row
    return result


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def run_promptguard_formal(
    *,
    freeze_path: Path = DEFAULT_FREEZE,
    output_dir: Path = DEFAULT_OUTPUT,
    device_request: str = "auto",
    resume: bool = False,
) -> dict[str, Any]:
    freeze_path = freeze_path.resolve()
    output_dir = output_dir.resolve()
    freeze, inputs = validate_freeze(freeze_path)
    freeze_sha256 = sha256_file(freeze_path)
    model_spec = freeze["model"]
    inference_spec = freeze["inference"]
    snapshot = Path(str(model_spec["snapshot_path"]))
    threshold = float(inference_spec["threshold"])
    max_length = int(inference_spec["max_length"])

    import torch
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "cuda" if device_request == "auto" and torch.cuda.is_available() else device_request
    if device == "auto":
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")

    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / "raw_predictions.jsonl"
    progress_path = output_dir / "progress.jsonl"
    failures_path = output_dir / "failures.jsonl"
    manifest_path = output_dir / "run_manifest.json"
    if predictions_path.exists() and not resume:
        raise FileExistsError("raw_predictions.jsonl exists; use --resume or a new output path")
    inputs_by_id = {str(row["case_id"]): row for row in inputs}
    existing = (
        _existing_predictions(
            predictions_path,
            freeze_sha256=freeze_sha256,
            inputs_by_id=inputs_by_id,
        )
        if resume and predictions_path.exists()
        else {}
    )

    started_at = _utc_now()
    load_started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(snapshot, local_files_only=True)
    mapping = binary_label_mapping(getattr(model.config, "id2label", None))
    model.to(device)
    model.eval()
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    load_ms = (time.perf_counter() - load_started) * 1000.0

    mode = "a" if existing else "w"
    new_rows: dict[str, dict[str, Any]] = {}
    with (
        predictions_path.open(mode, encoding="utf-8", newline="", buffering=1) as predictions_handle,
        progress_path.open("a", encoding="utf-8", newline="", buffering=1) as progress_handle,
        failures_path.open("a", encoding="utf-8", newline="", buffering=1) as failures_handle,
    ):
        for ordinal, input_row in enumerate(inputs, start=1):
            case_id = str(input_row["case_id"])
            if case_id in existing:
                continue
            case_started = time.perf_counter()
            progress_handle.write(
                json.dumps(
                    {
                        "timestamp": _utc_now(),
                        "ordinal": ordinal,
                        "total": len(inputs),
                        "case_id": case_id,
                        "status": "running",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
            try:
                windows = tokenizer_windows(
                    tokenizer, str(input_row["scan_text"]), max_length=max_length
                )
                chunk_scores: list[dict[str, Any]] = []
                for window in windows:
                    encoded = {
                        "input_ids": torch.tensor([window["input_ids"]], dtype=torch.long, device=device),
                        "attention_mask": torch.tensor(
                            [window["attention_mask"]], dtype=torch.long, device=device
                        ),
                    }
                    if device == "cuda":
                        torch.cuda.synchronize()
                    inference_started = time.perf_counter()
                    with torch.inference_mode():
                        logits = model(**encoded).logits[0]
                        probabilities = (
                            torch.softmax(logits.float(), dim=-1).detach().cpu().tolist()
                        )
                    if device == "cuda":
                        torch.cuda.synchronize()
                    inference_ms = (time.perf_counter() - inference_started) * 1000.0
                    if len(probabilities) != 2:
                        raise ValueError(
                            f"expected two PromptGuard probabilities, got {len(probabilities)}"
                        )
                    benign_probability = float(probabilities[0])
                    malicious_probability = float(probabilities[1])
                    if not all(
                        math.isfinite(value)
                        for value in (benign_probability, malicious_probability)
                    ) or abs(benign_probability + malicious_probability - 1.0) > 1e-5:
                        raise ValueError("non-finite or non-normalized classifier probabilities")
                    predicted_class = int(malicious_probability > benign_probability)
                    chunk_scores.append(
                        {
                            "window_index": window["window_index"],
                            "payload_token_count": window["payload_token_count"],
                            "encoded_token_count": window["encoded_token_count"],
                            "benign_probability": benign_probability,
                            "malicious_probability": malicious_probability,
                            "predicted_class_id": predicted_class,
                            "predicted_label": mapping[predicted_class],
                            "inference_ms": inference_ms,
                        }
                    )
                aggregate = max(row["malicious_probability"] for row in chunk_scores)
                decision = "malicious" if aggregate >= threshold else "benign"
                row = {
                    "schema_version": "paper-promptguard-detector-prediction-1.0",
                    "runner_version": RUNNER_VERSION,
                    "freeze_sha256": freeze_sha256,
                    "case_id": case_id,
                    "benchmark": str(input_row["benchmark"]),
                    "scan_text_sha256": str(input_row["scan_text_sha256"]),
                    "status": "completed",
                    "stub_used": False,
                    "window_count": len(chunk_scores),
                    "chunk_scores": chunk_scores,
                    "chunk_scores_sha256": rows_sha256(chunk_scores),
                    "aggregate_malicious_probability": aggregate,
                    "threshold": threshold,
                    "decision": decision,
                    "effective_decision": decision,
                    "failure_policy_applied": False,
                    "total_latency_ms": (time.perf_counter() - case_started) * 1000.0,
                    "completed_at": _utc_now(),
                }
            except Exception as exc:  # retain the case; never silently retry
                failure = {
                    "timestamp": _utc_now(),
                    "ordinal": ordinal,
                    "case_id": case_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": traceback.format_exc(),
                }
                failures_handle.write(
                    json.dumps(failure, ensure_ascii=False, sort_keys=True) + "\n"
                )
                row = {
                    "schema_version": "paper-promptguard-detector-prediction-1.0",
                    "runner_version": RUNNER_VERSION,
                    "freeze_sha256": freeze_sha256,
                    "case_id": case_id,
                    "benchmark": str(input_row["benchmark"]),
                    "scan_text_sha256": str(input_row["scan_text_sha256"]),
                    "status": "failed",
                    "stub_used": False,
                    "window_count": 0,
                    "chunk_scores": [],
                    "chunk_scores_sha256": rows_sha256([]),
                    "aggregate_malicious_probability": None,
                    "threshold": threshold,
                    "decision": "failure",
                    "effective_decision": "malicious",
                    "failure_policy_applied": True,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "total_latency_ms": (time.perf_counter() - case_started) * 1000.0,
                    "completed_at": _utc_now(),
                }
            predictions_handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            progress_handle.write(
                json.dumps(
                    {
                        "timestamp": _utc_now(),
                        "ordinal": ordinal,
                        "total": len(inputs),
                        "case_id": case_id,
                        "status": row["status"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
            new_rows[case_id] = row

    predictions_by_id = dict(existing)
    predictions_by_id.update(new_rows)
    ordered = [predictions_by_id[str(row["case_id"])] for row in inputs if str(row["case_id"]) in predictions_by_id]
    write_jsonl(predictions_path, ordered)
    completed_ids = [str(row["case_id"]) for row in ordered]
    successful = [row for row in ordered if row["status"] == "completed"]
    failed = [row for row in ordered if row["status"] == "failed"]
    latencies = [float(row["total_latency_ms"]) for row in ordered]
    peak_gpu_bytes = int(torch.cuda.max_memory_allocated()) if device == "cuda" else 0
    raw_id2label = {
        str(key): str(value) for key, value in getattr(model.config, "id2label", {}).items()
    }
    del model
    del tokenizer
    if device == "cuda":
        torch.cuda.empty_cache()

    checks = {
        "all_frozen_cases_accounted": len(ordered) == len(inputs)
        and set(completed_ids) == set(inputs_by_id),
        "unique_prediction_ids": len(completed_ids) == len(set(completed_ids)),
        "all_rows_match_freeze": all(row["freeze_sha256"] == freeze_sha256 for row in ordered),
        "all_rows_match_input_hash": all(
            row["scan_text_sha256"] == inputs_by_id[row["case_id"]]["scan_text_sha256"]
            for row in ordered
        ),
        "no_stub_rows": all(row.get("stub_used") is False for row in ordered),
        "successful_rows_have_complete_windows": all(
            row["window_count"] == len(row["chunk_scores"]) and row["window_count"] > 0
            for row in successful
        ),
        "failed_rows_retained_fail_closed": all(
            row["effective_decision"] == "malicious" and row["failure_policy_applied"]
            for row in failed
        ),
        "label_file_not_read_by_runner": True,
    }
    eligible = all(checks.values())
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "status": "completed" if eligible else "failed_completeness_gate",
        "started_at": started_at,
        "completed_at": _utc_now(),
        "freeze_path": str(freeze_path),
        "freeze_sha256": freeze_sha256,
        "freeze_created_at": freeze["created_at"],
        "freeze_created_before_run": str(freeze["created_at"]) < started_at,
        "model": {
            "model_id": model_spec["model_id"],
            "revision": model_spec["revision"],
            "snapshot_path": str(snapshot),
            "local_files_only": True,
            "raw_id2label": raw_id2label,
            "resolved_id2label": {str(key): value for key, value in mapping.items()},
        },
        "runtime": {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
            "transformers_version": transformers.__version__,
            "device": device,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else "",
            "model_load_ms": load_ms,
            "peak_gpu_memory_bytes": peak_gpu_bytes,
        },
        "config": dict(inference_spec),
        "summary": {
            "expected_case_count": len(inputs),
            "prediction_count": len(ordered),
            "successful_case_count": len(successful),
            "failed_case_count": len(failed),
            "resumed_case_count": len(existing),
            "new_case_count": len(new_rows),
            "total_window_count": sum(int(row["window_count"]) for row in ordered),
            "latency_ms_median": _percentile(latencies, 0.5),
            "latency_ms_p95": _percentile(latencies, 0.95),
            "checks": checks,
            "checks_passed": eligible,
        },
        "output_files": {
            "raw_predictions": str(predictions_path),
            "raw_predictions_sha256": sha256_file(predictions_path),
            "predictions_rows_sha256": rows_sha256(ordered),
            "progress": str(progress_path),
            "progress_sha256": sha256_file(progress_path),
            "failures": str(failures_path),
            "failures_sha256": sha256_file(failures_path),
        },
        "labels_loaded_during_inference": False,
        "result_eligible_for_formal_tables": eligible,
        "eligible_table_scope": ["detector_performance"],
        "ineligible_table_scope": ["end_to_end_agent_asr", "agent_tcr", "tool_execution_utility"],
        "boundary": (
            "Source-backed detector-only inference over the pre-run frozen 3,280-case universe. "
            "Formal eligibility is limited to detector-performance tables; this run is not an "
            "end-to-end agent defense experiment."
        ),
    }
    _write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_promptguard_formal(
        freeze_path=args.freeze,
        output_dir=args.output_dir,
        device_request=args.device,
        resume=args.resume,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "summary": manifest["summary"],
                "result_eligible_for_formal_tables": manifest[
                    "result_eligible_for_formal_tables"
                ],
                "eligible_table_scope": manifest["eligible_table_scope"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
