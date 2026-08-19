"""Directly smoke-test the official AgentDojo detector on a preserved long tool output.

This smoke is a recovery diagnostic for the official transformers PI-detector
condition.  It extracts the longest tool-output text from the preserved failed
AgentDojo trace, unloads the local Ollama target model, and calls the pinned
official ``TransformersBasedPIDetector.detect`` method on the complete text.

It does not execute a benchmark case, does not truncate detector input, and is
never eligible for formal result tables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import sha256_file
from .run_agentdojo_official_detector_formal import (
    _apply_detector_device_policy,
    _ollama_unload,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AGENTDOJO = ROOT / "external" / "benchmarks" / "agentdojo"
DEFAULT_FAILED_TRACE = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_official_formal_v2_cpu_detector"
    / "official_logs"
    / "openai-compatible-transformers_pi_detector"
    / "workspace"
    / "user_task_25"
    / "none"
    / "none.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_long_output_direct_smoke_v1"
)
DEFAULT_HF_HUB_CACHE = Path(r"E:\ai_cache\huggingface\hub")
DEFAULT_DOWNLOAD_SNAPSHOT = (
    Path(r"E:\M3_PI_Guard_runtime")
    / "agentdojo_transformers"
    / "evidence"
    / "protectai_detector_download_snapshot.json"
)
DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_TARGET_MODEL = "m3-paper-qwen3-8b-v1:latest"
MODEL_ID = "protectai/deberta-v3-base-prompt-injection-v2"
SMOKE_VERSION = "m3-paper-v1-agentdojo-transformers-long-output-direct-smoke-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tool_text_blocks(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for message_index, message in enumerate(trace.get("messages", [])):
        if not isinstance(message, Mapping) or message.get("role") != "tool":
            continue
        tool_call = message.get("tool_call")
        function_name = ""
        if isinstance(tool_call, Mapping):
            function_name = str(tool_call.get("function", ""))
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for block_index, block in enumerate(content):
            if not isinstance(block, Mapping):
                continue
            if block.get("type") != "text":
                continue
            text = str(block.get("content", ""))
            blocks.append(
                {
                    "message_index": message_index,
                    "block_index": block_index,
                    "function": function_name,
                    "char_count": len(text),
                    "sha256": _text_sha256(text),
                    "text": text,
                }
            )
    return blocks


def extract_longest_tool_output(trace_path: Path, *, minimum_chars: int) -> dict[str, Any]:
    trace = _read_json(trace_path)
    blocks = _tool_text_blocks(trace)
    if not blocks:
        raise ValueError("trace contains no text tool-output blocks")
    longest = max(blocks, key=lambda row: int(row["char_count"]))
    if int(longest["char_count"]) < minimum_chars:
        raise ValueError(
            "longest tool output is shorter than the required diagnostic threshold: "
            f"{longest['char_count']} < {minimum_chars}"
        )
    return {
        "suite_name": trace.get("suite_name", ""),
        "pipeline_name": trace.get("pipeline_name", ""),
        "user_task_id": trace.get("user_task_id", ""),
        "injection_task_id": trace.get("injection_task_id"),
        "tool_block_count": len(blocks),
        "selected": longest,
    }


def _write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    detector = manifest.get("detector", {})
    selected = manifest.get("selected_tool_output", {})
    lines = [
        "# AgentDojo transformers_pi_detector long-output direct smoke v1",
        "",
        f"- Status: `{manifest['status']}`",
        "- Result eligible for formal tables: `False`",
        f"- Source trace: `{manifest['source_trace_path']}`",
        f"- Selected tool function: `{selected.get('function', '')}`",
        f"- Selected char count: `{selected.get('char_count', 0)}`",
        f"- Token count: `{selected.get('token_count', '')}`",
        f"- Detector device: `{detector.get('device', '')}`",
        f"- Detector decision: `{detector.get('is_injection', '')}`",
        f"- Safety score: `{detector.get('safety_score', '')}`",
        "",
        "## Boundary",
        "",
        str(manifest["boundary"]),
        "",
    ]
    if manifest.get("error"):
        lines.extend(["## Error", "", f"- Type: `{manifest.get('error_type')}`", f"- Message: `{manifest.get('error')}`", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_smoke(
    *,
    agentdojo_checkout: Path,
    hf_hub_cache: Path,
    download_snapshot: Path,
    source_trace: Path,
    output_dir: Path,
    base_url: str,
    target_model: str,
    minimum_chars: int,
) -> dict[str, Any]:
    source_root = agentdojo_checkout / "src"
    sys.path.insert(0, str(source_root))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_CACHE"] = str(hf_hub_cache)
    os.environ["HF_HOME"] = str(hf_hub_cache.parent)
    device_policy = _apply_detector_device_policy("cpu")
    download = _read_json(download_snapshot)
    extracted = extract_longest_tool_output(source_trace, minimum_chars=minimum_chars)
    selected = dict(extracted["selected"])
    tool_output = str(selected.pop("text"))
    manifest: dict[str, Any] = {
        "schema_version": "paper-agentdojo-transformers-long-output-direct-smoke-1.0",
        "smoke_version": SMOKE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Recovery diagnostic only. The smoke calls AgentDojo's pinned official "
            "TransformersBasedPIDetector.detect on the complete preserved tool-output "
            "text. It does not execute AgentDojo benchmark tasks, does not truncate "
            "detector input and cannot support ASR, TCR, utility or SOTA claims."
        ),
        "source_trace_path": str(source_trace.resolve()),
        "source_trace_sha256": sha256_file(source_trace),
        "download_snapshot": str(download_snapshot.resolve()),
        "download_snapshot_sha256": sha256_file(download_snapshot),
        "model_id": MODEL_ID,
        "resolved_revision": download.get("resolved_revision", ""),
        "snapshot_path": download.get("snapshot_path", ""),
        "hf_hub_cache": str(hf_hub_cache.resolve()),
        "agentdojo_checkout": str(agentdojo_checkout.resolve()),
        "agentdojo_pi_detector_sha256": sha256_file(
            agentdojo_checkout
            / "src"
            / "agentdojo"
            / "agent_pipeline"
            / "pi_detector.py"
        ),
        "device_policy": device_policy,
        "ollama_resource_policy": {
            "policy": "unload_ollama_before_detector",
            "target_model": target_model,
            "base_url": base_url,
        },
        "trace_metadata": {
            key: extracted.get(key)
            for key in [
                "suite_name",
                "pipeline_name",
                "user_task_id",
                "injection_task_id",
                "tool_block_count",
            ]
        },
        "selected_tool_output": selected,
        "python_executable": sys.executable,
        "environment": {
            "HF_HOME": os.environ.get("HF_HOME", ""),
            "HF_HUB_CACHE": os.environ.get("HF_HUB_CACHE", ""),
            "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", ""),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        },
    }

    try:
        unload_started = time.perf_counter()
        unload = _ollama_unload(base_url, target_model)
        unload_latency_ms = (time.perf_counter() - unload_started) * 1000.0
        from agentdojo.agent_pipeline.pi_detector import TransformersBasedPIDetector

        load_started = time.perf_counter()
        detector = TransformersBasedPIDetector()
        load_latency_ms = (time.perf_counter() - load_started) * 1000.0
        manifest["ollama_resource_policy"]["unload"] = unload
        manifest["ollama_resource_policy"]["unload_latency_ms"] = unload_latency_ms
        manifest["detector"] = {
            "class": "agentdojo.agent_pipeline.pi_detector.TransformersBasedPIDetector",
            "model_name": detector.model_name,
            "safe_label": detector.safe_label,
            "threshold": detector.threshold,
            "mode": detector.mode,
            "device": str(getattr(detector.pipeline, "device", "")),
            "load_latency_ms": load_latency_ms,
        }
        tokenizer = getattr(detector.pipeline, "tokenizer", None)
        token_count = None
        if tokenizer is not None:
            tokenized = tokenizer(tool_output, add_special_tokens=True)
            token_count = len(tokenized.get("input_ids", []))
        manifest["selected_tool_output"]["token_count"] = token_count
        detect_started = time.perf_counter()
        is_injection, safety_score = detector.detect(tool_output)
        detect_latency_ms = (time.perf_counter() - detect_started) * 1000.0
        manifest["status"] = "completed_long_output_direct_smoke"
        manifest["detector"].update(
            {
                "detect_latency_ms": detect_latency_ms,
                "is_injection": bool(is_injection),
                "safety_score": float(safety_score),
            }
        )
    except Exception as exc:  # pragma: no cover - exercised by real smoke failures.
        manifest["status"] = "failed_long_output_direct_smoke"
        manifest["error_type"] = type(exc).__name__
        manifest["error"] = str(exc)
        manifest["traceback"] = traceback.format_exc()

    manifest_path = output_dir / "smoke_manifest.json"
    report_path = output_dir / "smoke_report.md"
    _write_json(manifest_path, manifest)
    _write_markdown(report_path, manifest)
    manifest["artifacts"] = {
        "manifest": str(manifest_path.resolve()),
        "report": str(report_path.resolve()),
    }
    _write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agentdojo-checkout", type=Path, default=DEFAULT_AGENTDOJO)
    parser.add_argument("--hf-hub-cache", type=Path, default=DEFAULT_HF_HUB_CACHE)
    parser.add_argument("--download-snapshot", type=Path, default=DEFAULT_DOWNLOAD_SNAPSHOT)
    parser.add_argument("--source-trace", type=Path, default=DEFAULT_FAILED_TRACE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--target-model", default=DEFAULT_TARGET_MODEL)
    parser.add_argument("--minimum-chars", type=int, default=10_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = run_smoke(
        agentdojo_checkout=args.agentdojo_checkout,
        hf_hub_cache=args.hf_hub_cache,
        download_snapshot=args.download_snapshot,
        source_trace=args.source_trace,
        output_dir=args.output_dir,
        base_url=args.base_url,
        target_model=args.target_model,
        minimum_chars=args.minimum_chars,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "selected_chars": manifest["selected_tool_output"].get("char_count", 0),
                "token_count": manifest["selected_tool_output"].get("token_count"),
                "detector_device": manifest.get("detector", {}).get("device", ""),
                "output": manifest["artifacts"]["manifest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if manifest["status"] == "completed_long_output_direct_smoke" else 1


if __name__ == "__main__":
    raise SystemExit(main())
