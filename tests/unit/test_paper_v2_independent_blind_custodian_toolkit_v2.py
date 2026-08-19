from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import experiments.paper_v2.independent_blind_custodian_toolkit_v2 as toolkit


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _run_toolkit_python(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def _files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_builds_label_empty_hash_bound_runnable_tree(tmp_path: Path) -> None:
    root = tmp_path / "M3_Blind_Custodian_v2"
    manifest = toolkit.build_custodian_toolkit(root)

    assert manifest["status"] == "sealed_label_empty_toolkit"
    assert manifest["frozen_slots"] == {
        "rows": 600,
        "sha256": toolkit.FROZEN_SLOTS_SHA256,
    }
    assert manifest["evidence_boundary"] == {
        "source_enumeration_used": False,
        "source_allowlist_entries": len(toolkit.SOURCE_COPY_MAP),
        "real_authoring_pairs_copied": 0,
        "real_candidate_rows_copied": 0,
        "real_label_rows_copied": 0,
        "credentials_read": False,
        "configuration_files_copied": 0,
        "prior_outputs_copied": 0,
        "network_calls_made": 0,
    }
    for relative in toolkit.EMPTY_WORK_DIRS:
        directory = root.joinpath(*relative.split("/"))
        assert directory.is_dir()
        assert list(directory.iterdir()) == []

    expected_files = {
        *toolkit.SOURCE_COPY_MAP.values(),
        *toolkit._generated_files(),
        toolkit.TOOLKIT_MANIFEST_NAME,
    }
    assert _files(root) == expected_files
    assert not any(
        path.name.lower().startswith(".env")
        or "secret" in path.name.lower()
        or "credential" in path.name.lower()
        or "candidate" in path.name.lower()
        for path in root.rglob("*")
        if path.is_file()
    )
    slots = (
        root
        / "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl"
    )
    assert hashlib.sha256(slots.read_bytes()).hexdigest() == toolkit.FROZEN_SLOTS_SHA256

    verify = _run_toolkit_python(
        root,
        "scripts/verify_toolkit_v2.py",
        "--root",
        str(root),
        "--pristine",
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert json.loads(verify.stdout)["status"] == "toolkit_verified"

    module_help = _run_toolkit_python(
        root,
        "-m",
        "experiments.paper_v2.independent_blind_closeout_v2",
        "--help",
    )
    assert module_help.returncode == 0, module_help.stderr
    assert "validate-pre-release" in module_help.stdout

    assert "build-unsigned-registration" in module_help.stdout
    assert "verify-signature-receipt" in module_help.stdout
    assert "seal-scoring-results" in module_help.stdout
    assert "build-unsigned-scoring-attestation" in module_help.stdout
    assert "verify-scoring-attestation" in module_help.stdout
    assert str(REPOSITORY_ROOT) not in module_help.stdout
    assert "standalone custodian toolkit root" in module_help.stdout


def test_refuses_existing_relative_and_traversing_output(tmp_path: Path) -> None:
    root = tmp_path / "single-use"
    toolkit.build_custodian_toolkit(root)
    with pytest.raises(toolkit.CustodianToolkitV2Error, match="already exists"):
        toolkit.build_custodian_toolkit(root)
    with pytest.raises(toolkit.CustodianToolkitV2Error, match="absolute"):
        toolkit.build_custodian_toolkit(Path("relative-toolkit"))
    with pytest.raises(toolkit.CustodianToolkitV2Error, match="traversal"):
        toolkit.build_custodian_toolkit(tmp_path / "parent" / ".." / "escape")


@pytest.mark.parametrize(
    "relative",
    ["../escape", "safe/../../escape", "/absolute", r"safe\windows-escape"],
)
def test_rejects_toolkit_relative_path_escape(relative: str) -> None:
    with pytest.raises(toolkit.CustodianToolkitV2Error, match="unsafe"):
        toolkit._safe_relative_path(relative)


def test_hash_verifier_rejects_immutable_tamper(tmp_path: Path) -> None:
    root = tmp_path / "tamper-check"
    toolkit.build_custodian_toolkit(root)
    readme = root / "README_CUSTODIAN_ZH.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")

    verify = _run_toolkit_python(
        root,
        "scripts/verify_toolkit_v2.py",
        "--root",
        str(root),
        "--pristine",
    )
    assert verify.returncode == 2
    result = json.loads(verify.stdout)
    assert result["status"] == "toolkit_rejected"
    assert result["checks"]["file_01_sha256"] is False


def test_source_read_boundary_is_exact_and_excludes_local_state() -> None:
    assert len(toolkit.SOURCE_COPY_MAP) == 10
    assert set(toolkit.SOURCE_COPY_MAP) == set(toolkit.SOURCE_COPY_MAP.values())
    for relative in toolkit.SOURCE_COPY_MAP:
        lowered_parts = {part.lower() for part in Path(relative).parts}
        assert "config" not in lowered_parts
        assert "outputs" not in lowered_parts
        assert not any(part.startswith(".env") for part in lowered_parts)
        assert not any("secret" in part for part in lowered_parts)
        assert not any("credential" in part for part in lowered_parts)
        assert not any("candidate" in part for part in lowered_parts)


def test_generated_contract_matches_project_canonical_json() -> None:
    from experiments.paper_v2.contracts import canonical_json_bytes

    namespace: dict[str, object] = {}
    exec(toolkit._STANDALONE_CONTRACTS, namespace)  # noqa: S102 - static source constant
    standalone = namespace["canonical_json_bytes"]
    value = {"中文": [3, 1], "a": {"x": True}}
    assert callable(standalone)
    assert standalone(value) == canonical_json_bytes(value)


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 unavailable")
def test_all_generated_powershell_scripts_parse(tmp_path: Path) -> None:
    root = tmp_path / "powershell-parse"
    toolkit.build_custodian_toolkit(root)
    parser_command = (
        "& { param([string]$Target) $tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile(" 
        "$Target,[ref]$tokens,[ref]$errors) | Out-Null; "
        "if ($errors.Count -ne 0) { $errors | ForEach-Object { Write-Error $_ }; exit 2 } }"
    )
    for script in sorted((root / "scripts").glob("*.ps1")):
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", parser_command, str(script)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        assert result.returncode == 0, f"{script.name}: {result.stdout}{result.stderr}"


@pytest.mark.skipif(
    shutil.which("pwsh") is None or shutil.which("openssl") is None,
    reason="PowerShell 7 or OpenSSL unavailable",
)
def test_external_ed25519_helper_signs_raw_digest_without_copying_key(
    tmp_path: Path,
) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    root = tmp_path / "signature-helper"
    toolkit.build_custodian_toolkit(root)
    private_key = tmp_path / "outside-toolkit-ed25519-private.pem"
    public_key = root / "release/custodian_public_key.pem"
    unsigned = root / "signatures/unsigned_registration_v2.json"
    signature_path = root / "signatures/registration_signature_base64.txt"
    digest = hashlib.sha256(b"synthetic-registration-payload").hexdigest()
    unsigned.write_text(
        json.dumps({"registration_signature_payload_sha256": digest}),
        encoding="utf-8",
    )
    generate = subprocess.run(
        [
            "openssl",
            "genpkey",
            "-algorithm",
            "ED25519",
            "-out",
            str(private_key),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert generate.returncode == 0, generate.stderr
    export = subprocess.run(
        [
            "openssl",
            "pkey",
            "-in",
            str(private_key),
            "-pubout",
            "-out",
            str(public_key),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert export.returncode == 0, export.stderr
    sign = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(root / "scripts/SIGN_EXTERNAL_ED25519_DIGEST.ps1"),
            "-OpenSSLExe",
            "openssl",
            "-PrivateKeyPath",
            str(private_key),
            "-UnsignedJsonPath",
            str(unsigned),
            "-DigestField",
            "registration_signature_payload_sha256",
            "-SignatureOutputPath",
            str(signature_path),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert sign.returncode == 0, sign.stdout + sign.stderr
    signature = base64.b64decode(signature_path.read_text(encoding="utf-8").strip())
    assert len(signature) == 64
    loaded = serialization.load_pem_public_key(public_key.read_bytes())
    assert isinstance(loaded, Ed25519PublicKey)
    loaded.verify(signature, bytes.fromhex(digest))
    assert private_key.is_file()
    assert not any(path.name == private_key.name for path in root.rglob("*"))
