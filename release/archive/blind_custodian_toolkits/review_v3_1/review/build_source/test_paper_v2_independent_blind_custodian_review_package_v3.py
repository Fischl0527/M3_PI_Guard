from __future__ import annotations

import base64
import hashlib
import importlib.util
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from experiments.paper_v2.independent_blind_custodian_review_package_v3 import (
    FROZEN_SLOTS_SHA256,
    MANIFEST_NAME,
    ReviewPackageV3Error,
    SOURCE_COPY_MAP,
    build_review_package,
    canonical_json_bytes,
    generated_files,
)


def run_cli(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "custodian.py", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def build(tmp_path: Path) -> Path:
    root = tmp_path / "review-package-v3"
    build_review_package(root)
    return root


def load_packaged_cli(root: Path) -> object:
    spec = importlib.util.spec_from_file_location(
        f"custodian_v3_{hash(root)}",
        root / "custodian.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest_digest(value: dict[str, object]) -> str:
    core = {key: item for key, item in value.items() if key != "manifest_sha256"}
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def test_builder_is_explicit_label_empty_python_first_and_single_use(
    tmp_path: Path,
) -> None:
    root = build(tmp_path)
    manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    paths = {row["path"] for row in manifest["files"]}
    assert paths == set(SOURCE_COPY_MAP.values()) | set(generated_files())
    assert manifest["frozen_slots"]["sha256"] == FROZEN_SLOTS_SHA256
    assert manifest["evidence_boundary"] == {
        "source_enumeration_used": False,
        "source_allowlist_entries": len(SOURCE_COPY_MAP),
        "real_authoring_pairs_copied": 0,
        "real_candidate_rows_copied": 0,
        "real_label_rows_copied": 0,
        "credentials_read": False,
        "private_key_copied": False,
        "configuration_files_copied": 0,
        "prior_outputs_copied": 0,
        "powershell_wrappers_copied": 0,
        "network_calls_made": 0,
    }
    assert not list(root.rglob("*.ps1"))
    assert not list(root.rglob("*.pem"))
    assert {path for path in paths if Path(path).name == "README.md"} == {
        "README.md",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/README.md",
    }
    assert "唯一权威的操作入口" in (root / "README.md").read_text(
        encoding="utf-8"
    )
    assert {
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/effect_receipt_entry_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/provider_trace_receipt_entry_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/provider_request_chain_started_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/provider_request_chain_terminal_template.json",
        "review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2/scoring_integrity_verifier_receipt_template.json",
    }.issubset(paths)
    assert not any(
        token in path.lower()
        for path in paths
        for token in ("authored_pairs.jsonl", "blind_labels", "output_package_v2")
    )
    with pytest.raises(ReviewPackageV3Error, match="overwrite refused"):
        build_review_package(root)
    with pytest.raises(ReviewPackageV3Error, match="must be absolute"):
        build_review_package(Path("relative-output"))


def test_pristine_and_standard_verification_have_fixed_work_boundary(
    tmp_path: Path,
) -> None:
    root = build(tmp_path)
    pristine = run_cli(root, "verify-pristine")
    assert pristine.returncode == 0, pristine.stderr
    assert json.loads(pristine.stdout)["status"] == "review_package_verified"
    private = root / "work/private/labels/do-not-report-this-name.jsonl"
    private.write_text("secret private label payload\n", encoding="utf-8")
    standard = run_cli(root, "verify")
    assert standard.returncode == 0, standard.stderr
    assert "do-not-report-this-name" not in standard.stdout + standard.stderr
    assert "secret private label payload" not in standard.stdout + standard.stderr
    polluted = run_cli(root, "verify-pristine")
    assert polluted.returncode == 2
    assert "do-not-report-this-name" not in polluted.stdout + polluted.stderr
    (root / "work/unknown-root-node").mkdir()
    assert run_cli(root, "verify-pristine").returncode == 2


def test_manifest_cannot_induce_private_read_or_accept_nested_extension(
    tmp_path: Path,
) -> None:
    root = build(tmp_path)
    private = root / "work/private/labels/trap.json"
    private.write_text('{"gold":"DO_NOT_READ"}\n', encoding="utf-8")
    path = root / MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"][0] = {
        "path": "work/private/labels/trap.json",
        "bytes": private.stat().st_size,
        "sha256": hashlib.sha256(private.read_bytes()).hexdigest(),
        "role": "explicitly_allowlisted_review_source",
    }
    manifest["evidence_boundary"]["labels"] = {"gold": "DO_NOT_READ"}
    manifest["manifest_sha256"] = manifest_digest(manifest)
    path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    rejected = run_cli(root, "verify")
    assert rejected.returncode == 2
    assert "DO_NOT_READ" not in rejected.stdout + rejected.stderr
    assert "trap.json" not in rejected.stdout + rejected.stderr


def test_immutable_tamper_extra_and_hardlink_fail_closed(tmp_path: Path) -> None:
    root = build(tmp_path)
    (root / "README.md").write_text("tampered\n", encoding="utf-8")
    assert run_cli(root, "verify").returncode == 2

    root = build_review_again(tmp_path, "extra-package")
    (root / "schemas/extra.json").write_text("{}\n", encoding="utf-8")
    assert run_cli(root, "verify").returncode == 2

    root = build_review_again(tmp_path, "hardlink-package")
    link = root / "schemas/hardlink-copy.json"
    try:
        os.link(root / "schemas/review_package_config.schema.json", link)
    except OSError:
        pytest.skip("hard links are unavailable on this filesystem")
    assert run_cli(root, "verify").returncode == 2


@pytest.mark.skipif(os.name != "nt", reason="NTFS alternate stream test is Windows-only")
def test_immutable_alternate_data_stream_fails_closed(tmp_path: Path) -> None:
    root = build(tmp_path)
    ads = Path(str(root / "README.md") + ":m3-hidden")
    try:
        ads.write_text("hidden payload", encoding="utf-8")
    except OSError:
        pytest.skip("alternate data streams are unavailable on this filesystem")
    assert run_cli(root, "verify").returncode == 2


def build_review_again(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    build_review_package(root)
    return root


def test_config_alias_fails_even_with_rehashed_manifest(tmp_path: Path) -> None:
    root = build(tmp_path)
    config_path = root / "review_package_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["paths"]["label_file"] = config["paths"]["execution_set"]
    config_path.write_bytes(canonical_json_bytes(config) + b"\n")
    manifest_path = root / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    for entry in manifest["files"]:
        if entry["path"] == "review_package_config.json":
            entry["bytes"] = config_path.stat().st_size
            entry["sha256"] = config_sha
    manifest["critical_bindings"]["review_package_config_sha256"] = config_sha
    manifest["manifest_sha256"] = manifest_digest(manifest)
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    status = run_cli(root, "status")
    assert status.returncode == 2
    assert "path mapping is not exact" in status.stderr


def test_cli_surface_has_no_plaintext_keygen_or_formal_time_override(
    tmp_path: Path,
) -> None:
    root = build(tmp_path)
    help_result = run_cli(root, "--help")
    assert help_result.returncode == 0
    text = help_result.stdout.lower()
    assert "export-signing-request" in text
    assert "import-detached-signature" in text
    assert "sign-request" in text
    assert "scoring-attestation-verify-integrity-only" in text
    assert "keygen" not in text
    assert "--private-key" not in text
    assert "--at" not in text
    assert "setx" not in text
    assert not list(root.rglob("*.ps1"))
    config = json.loads((root / "review_package_config.json").read_text())
    assert "private_key" not in config["paths"]


def test_scoring_release_is_atomic_exact_and_bound_to_private_original(
    tmp_path: Path,
) -> None:
    root = build(tmp_path)
    cli = load_packaged_cli(root)
    private = root / "work/private/scoring/scoring_results_v2.jsonl"
    row = b'{"schema_version":"test-only"}\n'
    private.write_bytes(row * 3600)
    private_sha = hashlib.sha256(private.read_bytes()).hexdigest()
    seal = {
        "scoring_results": {
            "filename": "scoring_results_v2.jsonl",
            "rows": 3600,
            "sha256": private_sha,
            "unsafe_effect_true_count": 0,
            "task_completion_true_count": 0,
        }
    }
    cli.atomic_stage_scoring_release(seal)
    release = root / "work/generated/release/scoring_release_v3"
    assert {path.name for path in release.iterdir()} == {
        "scoring_results_v2.jsonl",
        "custodian_scoring_result_seal_v2.json",
    }
    assert cli.verify_scoring_release_pair(
        compare_private_original=True
    ) == seal
    with pytest.raises(cli.CustodianCLIError, match="overwrite refused"):
        cli.atomic_stage_scoring_release(seal)
    (release / "unexpected.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(cli.CustodianCLIError, match="file set is not exact"):
        cli.verify_scoring_release_pair(compare_private_original=False)
    (release / "unexpected.json").unlink()
    private.write_bytes(row * 3599 + b'{"tampered":true}\n')
    with pytest.raises(cli.CustodianCLIError, match="hashes differ"):
        cli.verify_scoring_release_pair(compare_private_original=True)


def test_developer_safe_core_and_cli_surface_accept_no_private_paths(
    tmp_path: Path,
) -> None:
    root = build(tmp_path)
    cli = load_packaged_cli(root)
    source_root = root / "review_source"
    sys.path.insert(0, str(source_root))
    try:
        from experiments.paper_v2 import independent_blind_closeout_v2 as closeout

        parameters = set(
            inspect.signature(
                closeout.verify_scoring_attestation_integrity_only
            ).parameters
        )
    finally:
        sys.path.remove(str(source_root))
    assert parameters == {
        "scoring_attestation_path",
        "scoring_result_seal_path",
        "scoring_results_release_path",
        "custody_manifest_path",
        "registration_path",
        "registration_verifier_receipt_path",
        "public_key_path",
        "verifier_id",
        "verified_at",
    }
    forbidden = {
        "authored_pairs",
        "identity_attestation",
        "label_file",
        "private_audit_dir",
        "scoring_results",
    }
    for function in (
        cli.command_scoring_attestation_verify_integrity_only,
        cli.replay_developer_safe_integrity,
        cli.command_stage_developer_safe_final,
        cli.developer_safe_final_sources,
    ):
        source = inspect.getsource(function)
        assert not any(f'configured_path("{name}")' in source for name in forbidden)


def test_developer_safe_cli_route_traps_every_private_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = build(tmp_path)
    cli = load_packaged_cli(root)
    original_configured_path = cli.configured_path
    original_read_json = cli.read_json
    scoring_attestation_path = original_configured_path("scoring_attestation")
    resolved: list[Path] = []

    def guarded_configured_path(name: str) -> Path:
        path = original_configured_path(name)
        if path.is_relative_to(root / "work/private"):
            raise AssertionError("developer-safe route constructed a private path")
        resolved.append(path)
        return path

    class IntegrityOnlyCore:
        @staticmethod
        def verify_scoring_attestation_integrity_only(
            **kwargs: object,
        ) -> dict[str, object]:
            assert all(
                not isinstance(value, Path)
                or not value.is_relative_to(root / "work/private")
                for value in kwargs.values()
            )
            return {
                "status": "developer_safe_scoring_signature_integrity_verified",
                "verifier_id": kwargs["verifier_id"],
                "verified_at": kwargs["verified_at"],
                "evidence_boundary": {
                    "verification_scope": (
                        "developer_safe_signature_integrity_only"
                    ),
                    "private_label_payload_opened": False,
                    "private_path_arguments_accepted": False,
                    "private_paths_enumerated": False,
                    "scientific_outcomes_read": 3600,
                    "scoring_semantics_recomputed": False,
                },
            }

    monkeypatch.setattr(cli, "configured_path", guarded_configured_path)
    monkeypatch.setattr(
        cli,
        "verify_scoring_release_pair",
        lambda *, compare_private_original: {},
    )
    monkeypatch.setattr(cli, "import_closeout", lambda: IntegrityOnlyCore)
    monkeypatch.setattr(
        cli,
        "read_json",
        lambda path: (
            {"custodian_id": "Custodian A"}
            if path == scoring_attestation_path
            else original_read_json(path)
        ),
    )
    written: dict[str, object] = {}
    monkeypatch.setattr(
        cli,
        "write_json_new",
        lambda path, value: written.update({"path": path, "value": value}),
    )
    result = cli.command_scoring_attestation_verify_integrity_only(
        SimpleNamespace(verifier_id="Verifier B")
    )
    assert result["status"] == (
        "developer_safe_scoring_signature_integrity_verified"
    )
    assert written["path"] == original_configured_path(
        "developer_safe_integrity_receipt"
    )
    assert resolved


def test_registration_external_signature_flow_and_distinct_verifier(
    tmp_path: Path,
) -> None:
    root = build(tmp_path)
    external = tmp_path / "external-signer"
    external.mkdir()
    private_key = Ed25519PrivateKey.generate()
    public_path = external / "public.pem"
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    assert run_cli(
        root,
        "register-public-key",
        "--public-key",
        str(public_path),
    ).returncode == 0
    assert run_cli(root, "prepare-identity-template").returncode == 0
    identity = root / "work/private/registration/offline_identity_attestation.txt"
    identity.write_text(
        "保管人稳定身份：Custodian A\n独立性确认：是\n",
        encoding="utf-8",
    )
    build_result = run_cli(
        root,
        "registration-build",
        "--custodian-id",
        "Custodian A",
        "--project-relationship",
        "External reviewer",
    )
    assert build_result.returncode == 0, build_result.stderr
    request_path = external / "registration_request.json"
    assert run_cli(
        root,
        "export-signing-request",
        "--stage",
        "registration",
        "--output",
        str(request_path),
    ).returncode == 0
    request = json.loads(request_path.read_text(encoding="utf-8"))
    signature = private_key.sign(bytes.fromhex(request["payload_digest_sha256"]))
    signature_path = external / "registration_signature.txt"
    signature_path.write_bytes(base64.b64encode(signature) + b"\n")
    imported = run_cli(
        root,
        "import-detached-signature",
        "--stage",
        "registration",
        "--signature-file",
        str(signature_path),
    )
    assert imported.returncode == 0, imported.stderr
    assert str(external) not in imported.stdout
    assert run_cli(root, "registration-finalize").returncode == 0
    same = run_cli(
        root,
        "registration-verify",
        "--verifier-id",
        "Custodian A",
    )
    assert same.returncode == 2
    distinct = run_cli(
        root,
        "registration-verify",
        "--verifier-id",
        "Verifier B",
    )
    assert distinct.returncode == 0, distinct.stderr
    next_result = run_cli(root, "show-next")
    assert next_result.returncode == 0, next_result.stderr
    assert json.loads(next_result.stdout)["stage"] == "author_600_private_pairs"


def test_local_fallback_rejects_unencrypted_private_key_before_prompt(
    tmp_path: Path,
) -> None:
    root = build(tmp_path)
    external = tmp_path / "external-fallback"
    external.mkdir()
    key = Ed25519PrivateKey.generate()
    public_path = external / "public.pem"
    private_path = external / "unencrypted-private.pem"
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    run_cli(root, "register-public-key", "--public-key", str(public_path))
    run_cli(root, "prepare-identity-template")
    identity = root / "work/private/registration/offline_identity_attestation.txt"
    identity.write_text("身份：Custodian A\n独立：是\n", encoding="utf-8")
    run_cli(
        root,
        "registration-build",
        "--custodian-id",
        "Custodian A",
        "--project-relationship",
        "External reviewer",
    )
    request = external / "request.json"
    run_cli(
        root,
        "export-signing-request",
        "--stage",
        "registration",
        "--output",
        str(request),
    )
    rejected = run_cli(
        root,
        "sign-request",
        "--stage",
        "registration",
        "--request",
        str(request),
        "--encrypted-private-key",
        str(private_path),
        "--signature-out",
        str(external / "signature.txt"),
    )
    assert rejected.returncode == 2
    assert "refuses an unencrypted private key" in rejected.stderr
    assert str(private_path) not in rejected.stdout + rejected.stderr


def test_no_formal_command_accepts_at_override(tmp_path: Path) -> None:
    root = build(tmp_path)
    rejected = run_cli(
        root,
        "registration-build",
        "--custodian-id",
        "Custodian A",
        "--project-relationship",
        "External reviewer",
        "--at",
        "2026-01-01T00:00:00Z",
    )
    assert rejected.returncode != 0
    assert "unrecognized arguments" in rejected.stderr


def test_v2_builder_cli_fails_closed_as_superseded(tmp_path: Path) -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "experiments/paper_v2/independent_blind_custodian_toolkit_v2.py"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--output-dir",
            str(tmp_path / "deprecated-v2"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "superseded" in result.stderr
    assert not (tmp_path / "deprecated-v2").exists()
