"""针对 8GB 显存显卡串行实验的小型 Ollama 模型生命周期管理工具。

负责模型的显存加载、预热、显存卸载与垃圾回收，防止长周期评测显存溢出（OOM）。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from .catalog import ALL_MODELS, CORE_MODELS
from .manifest import REPO_ROOT, utc_now


KNOWN_WINDOWS_OLLAMA = Path(r"D:\Ollama\app\ollama.exe")
OLLAMA_API_ROOT = "http://127.0.0.1:11434"


def ollama_executable() -> str:
    discovered = shutil.which("ollama")
    if discovered:
        return discovered
    if KNOWN_WINDOWS_OLLAMA.exists():
        return str(KNOWN_WINDOWS_OLLAMA)
    raise FileNotFoundError("Ollama executable was not found on PATH or D:\\Ollama\\app")


def run_ollama(arguments: Iterable[str], *, timeout: float = 7200.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [ollama_executable(), *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def installed_models() -> dict[str, dict[str, str]]:
    completed = run_ollama(["list"], timeout=30.0)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    rows: dict[str, dict[str, str]] = {}
    lines = [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        rows[parts[0]] = {"id": parts[1], "size": " ".join(parts[2:4])}
    return rows


def missing_models(models: Iterable[str] = CORE_MODELS) -> list[str]:
    installed = installed_models()
    return [model for model in models if model not in installed]


def pull_model(model: str) -> None:
    if model not in ALL_MODELS:
        raise ValueError(f"model not in approved catalogue: {model}")
    completed = run_ollama(["pull", model])
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def stop_model(model: str) -> None:
    completed = run_ollama(["stop", model], timeout=60.0)
    if completed.returncode and "not found" not in (completed.stderr or "").lower():
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def gpu_snapshot() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"captured_at": utc_now(), "available": False, "reason": "nvidia-smi not found"}
    completed = subprocess.run(
        [
            executable,
            "--query-gpu=name,utilization.gpu,memory.used,memory.free,memory.total",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30.0,
        check=False,
    )
    values = [value.strip() for value in completed.stdout.strip().split(",")]
    if completed.returncode or len(values) != 5:
        return {
            "captured_at": utc_now(),
            "available": False,
            "reason": (completed.stderr or completed.stdout).strip(),
        }
    return {
        "captured_at": utc_now(),
        "available": True,
        "name": values[0],
        "utilization_percent": float(values[1]),
        "memory_used_mib": float(values[2]),
        "memory_free_mib": float(values[3]),
        "memory_total_mib": float(values[4]),
    }


def ollama_api_get(path: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """读取本地 Ollama API 端点，严禁访问远程主机。"""

    endpoint = f"{OLLAMA_API_ROOT}/{str(path).lstrip('/')}"
    try:
        with urllib.request.urlopen(endpoint, timeout=float(timeout)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "captured_at": utc_now(),
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(payload, dict):
        return {
            "captured_at": utc_now(),
            "available": False,
            "reason": "Ollama response is not an object",
        }
    return {"captured_at": utc_now(), "available": True, **payload}


def ollama_ps_snapshot() -> dict[str, Any]:
    """从 ``/api/ps`` 捕获常驻模型上下文与显存（VRAM）证据。"""

    payload = ollama_api_get("api/ps")
    models: list[dict[str, Any]] = []
    if payload.get("available"):
        for item in payload.get("models", []):
            if not isinstance(item, dict):
                continue
            models.append(
                {
                    key: item.get(key)
                    for key in (
                        "name",
                        "model",
                        "digest",
                        "size",
                        "size_vram",
                        "context_length",
                        "expires_at",
                    )
                }
            )
    return {
        "captured_at": payload.get("captured_at", utc_now()),
        "available": bool(payload.get("available")),
        "reason": payload.get("reason", ""),
        "models": models,
    }


def save_inventory(path: str | Path) -> dict[str, Any]:
    payload = {
        "captured_at": utc_now(),
        "approved_models": list(ALL_MODELS),
        "installed": installed_models(),
        "missing_core": missing_models(CORE_MODELS),
        "gpu": gpu_snapshot(),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "pull-missing", "stop"])
    parser.add_argument("--model", choices=ALL_MODELS)
    parser.add_argument("--output", default="outputs/experiments/model_inventory.json")
    args = parser.parse_args(argv)
    if args.action == "status":
        payload = save_inventory(args.output)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if payload["missing_core"] else 0
    if args.action == "stop":
        if not args.model:
            parser.error("--model is required for stop")
        stop_model(args.model)
        print(f"stopped {args.model}")
        return 0
    for model in missing_models(CORE_MODELS):
        print(f"pulling {model}")
        pull_model(model)
    save_inventory(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
