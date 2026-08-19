"""Run a bounded, diagnostic-only smoke over local Ollama model tags."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "m3-ollama-model-smoke-1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request(base_url: str, endpoint: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_smoke(
    *,
    base_url: str,
    models: list[str] | None,
    timeout: float,
    num_predict: int,
) -> dict[str, Any]:
    version = _request(base_url, "/api/version", None, timeout)
    tags = _request(base_url, "/api/tags", None, timeout)
    available = [str(row["name"]) for row in tags.get("models", [])]
    selected = available if not models else models
    rows: list[dict[str, Any]] = []

    for index, model in enumerate(selected, start=1):
        started = time.perf_counter()
        row: dict[str, Any] = {
            "model": model,
            "started_at": _utc_now(),
            "status": "failed",
        }
        try:
            if model not in available:
                raise ValueError("model tag is not present in /api/tags")
            shown = _request(base_url, "/api/show", {"model": model}, timeout)
            generated = _request(
                base_url,
                "/api/generate",
                {
                    "model": model,
                    "prompt": "Reply with exactly OK.",
                    "stream": False,
                    "keep_alive": 0,
                    "options": {"temperature": 0, "num_predict": num_predict},
                },
                timeout,
            )
            response_text = str(generated.get("response", ""))
            thinking_text = str(generated.get("thinking", ""))
            if not generated.get("done"):
                raise RuntimeError("generation did not report done=true")
            if not response_text.strip() and not thinking_text.strip():
                raise RuntimeError("generation returned neither response nor thinking text")
            details = shown.get("details") or {}
            model_info = shown.get("model_info") or {}
            row.update(
                {
                    "status": "passed",
                    "format": details.get("format"),
                    "family": details.get("family"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization_level": details.get("quantization_level"),
                    "context_length": next(
                        (
                            value
                            for key, value in model_info.items()
                            if str(key).endswith(".context_length")
                        ),
                        None,
                    ),
                    "done_reason": generated.get("done_reason"),
                    "response_length": len(response_text),
                    "thinking_length": len(thinking_text),
                    "prompt_eval_count": generated.get("prompt_eval_count"),
                    "eval_count": generated.get("eval_count"),
                    "total_duration_ns": generated.get("total_duration"),
                }
            )
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
            row["error_type"] = type(exc).__name__
            row["error"] = str(exc)
        row["wall_time_s"] = round(time.perf_counter() - started, 6)
        rows.append(row)
        print(
            json.dumps(
                {"progress": f"{index}/{len(selected)}", "model": model, "status": row["status"]},
                ensure_ascii=False,
            ),
            flush=True,
        )

    failed = [row["model"] for row in rows if row["status"] != "passed"]
    return {
        "schema": SCHEMA,
        "generated_at": _utc_now(),
        "evidence_boundary": "diagnostic_model_load_smoke_not_formal_benchmark_result",
        "base_url": base_url,
        "ollama_version": version.get("version"),
        "available_models": available,
        "selected_models": selected,
        "passed": len(rows) - len(failed),
        "failed": len(failed),
        "failed_models": failed,
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", action="append")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--num-predict", type=int, default=32)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_smoke(
        base_url=args.base_url,
        models=args.model,
        timeout=args.timeout,
        num_predict=args.num_predict,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": result["passed"], "failed": result["failed"], "output": str(args.output)}))
    return 0 if result["failed"] == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
