"""项目全局配置加载、环境变量解析与秘密凭据脱敏管理。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "project.local.env"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config" / "project.env.example"

KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HEX40_PATTERN = re.compile(r"^[0-9a-f]{40}$")
PLACEHOLDER_PREFIXES = ("__SET_", "__OPTIONAL_", "<SET_", "CHANGEME")

REQUIRED_SHARED_KEYS = (
    "M3_RUNTIME_ROOT",
    "HF_HOME",
    "HF_HUB_CACHE",
    "OLLAMA_MODELS",
    "M3_OLLAMA_BASE_URL",
    "PROMPTGUARD_MODEL_ID",
    "PROMPTGUARD_REVISION",
    "PROMPTGUARD_THRESHOLD",
    "PROMPTGUARD_CHUNK_TOKEN_LIMIT",
    "PROMPTGUARD_DOWNLOAD_SNAPSHOT",
)


class ProjectConfigError(ValueError):
    """项目配置解析或校验失败异常基类。"""


def _unquote(value: str, *, line_number: int) -> str:
    value = value.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'}:
        if len(value) < 2 or value[-1] != value[0]:
            raise ProjectConfigError(f"line {line_number}: unterminated quoted value")
        return value[1:-1]
    return value


def parse_env_file(path: Path | str) -> dict[str, str]:
    """解析本地 .env 环境变量配置文件。"""

    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"project configuration not found: {config_path}")

    parsed: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        config_path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ProjectConfigError(
                f"line {line_number}: expected KEY=VALUE, found no equals sign"
            )
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not KEY_PATTERN.fullmatch(key):
            raise ProjectConfigError(f"line {line_number}: invalid key {key!r}")
        if key in parsed:
            raise ProjectConfigError(f"line {line_number}: duplicate key {key}")
        value = _unquote(raw_value, line_number=line_number)
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ProjectConfigError(f"line {line_number}: value contains control data")
        parsed[key] = value
    return parsed


def is_placeholder(value: str | None) -> bool:
    normalized = str(value or "").strip().upper()
    return not normalized or normalized.startswith(PLACEHOLDER_PREFIXES)


def is_secret_key(key: str) -> bool:
    upper = key.upper()
    return upper.endswith(
        ("_TOKEN", "_SECRET", "_PASSWORD", "_API_KEY", "_PRIVATE_KEY")
    ) or upper in {"TOKEN", "SECRET", "PASSWORD", "API_KEY", "PRIVATE_KEY"}


def redacted_config(values: Mapping[str, str]) -> dict[str, str]:
    """返回已脱敏敏感密钥信息（API Keys、Tokens）的安全配置字典副本。"""

    result: dict[str, str] = {}
    for key, value in values.items():
        if is_secret_key(key):
            result[key] = "<placeholder>" if is_placeholder(value) else "<redacted:set>"
        else:
            result[key] = value
    return result


def validate_project_config(
    values: Mapping[str, str], *, require_promptguard_token: bool = False
) -> list[str]:
    """校验配置必需字段、占位符、修订SHA、数值和可选token格式；不检查目录存在或依赖可用性。"""

    errors: list[str] = []
    for key in REQUIRED_SHARED_KEYS:
        if key not in values or is_placeholder(values.get(key)):
            errors.append(f"{key} is missing or still a placeholder")

    revision = str(values.get("PROMPTGUARD_REVISION", "")).strip().lower()
    if revision and not is_placeholder(revision) and not HEX40_PATTERN.fullmatch(revision):
        errors.append("PROMPTGUARD_REVISION must be a 40-character lowercase Git SHA")

    try:
        threshold = float(values.get("PROMPTGUARD_THRESHOLD", ""))
        if not 0.0 <= threshold <= 1.0:
            raise ValueError
    except ValueError:
        errors.append("PROMPTGUARD_THRESHOLD must be between 0 and 1")

    try:
        chunk_limit = int(values.get("PROMPTGUARD_CHUNK_TOKEN_LIMIT", ""))
        if chunk_limit <= 0:
            raise ValueError
    except ValueError:
        errors.append("PROMPTGUARD_CHUNK_TOKEN_LIMIT must be a positive integer")

    if require_promptguard_token:
        token = str(values.get("HF_TOKEN", "")).strip()
        if is_placeholder(token):
            errors.append("HF_TOKEN is missing or still a placeholder")
        elif not token.startswith("hf_") or len(token) < 20:
            errors.append("HF_TOKEN does not look like a Hugging Face user token")

    return errors


def resolve_config_path(path: Path | str | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()
    configured = os.environ.get("M3_PROJECT_CONFIG", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_CONFIG_PATH.resolve()


def load_project_config(
    path: Path | str | None = None,
    *,
    override: bool = False,
) -> tuple[Path, dict[str, str]]:
    """每次读取配置文件并按override规则更新进程环境，返回路径与配置字典；不实现单例或缓存。"""

    config_path = resolve_config_path(path)
    values = parse_env_file(config_path)
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return config_path, values
