from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from m3_eval.figure_manifest import (
    FIGURE_MANIFEST_FILENAME,
    FigureManifestError,
    load_figure_manifest,
    sha256_file,
    write_figure_manifest,
)


def _assets(bundle: Path, prefix: str = "figure") -> dict[str, str]:
    (bundle / f"{prefix}.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    (bundle / f"{prefix}.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    (bundle / f"{prefix}.svg").write_text("<svg><text>fixture</text></svg>\n", encoding="utf-8")
    return {
        "data": f"{prefix}.csv",
        "png": f"{prefix}.png",
        "svg": f"{prefix}.svg",
    }


def _figure(files: dict[str, str], *, figure_id: str = "primary", order: int = 10) -> dict:
    return {
        "id": figure_id,
        "title": "Fixture figure",
        "role": "primary",
        "order": order,
        "chart_type": "fixture_chart",
        "caption": "A strict local fixture.",
        "files": files,
        "metrics": ["ASR"],
        "grain": ["condition_id"],
        "uncertainty": [
            {
                "metric": "ASR",
                "method": "wilson",
                "level": 0.95,
                "low_field": "ci_low",
                "high_field": "ci_high",
            }
        ],
        "warnings": [],
    }


def test_writer_and_loader_roundtrip_hashes_and_sort_figures(tmp_path: Path) -> None:
    bundle = tmp_path / "E4"
    bundle.mkdir()
    second = _assets(bundle, "second")
    first = _assets(bundle, "first")

    path = write_figure_manifest(
        bundle,
        experiment_id="E4",
        evidence_tier="formal_model",
        figures=[
            _figure(second, figure_id="second", order=20),
            _figure(first, figure_id="first", order=10),
        ],
    )

    assert path == bundle / FIGURE_MANIFEST_FILENAME
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert [row["id"] for row in on_disk["figures"]] == ["first", "second"]
    data_entry = on_disk["figures"][0]["files"]["data"]
    assert data_entry == {
        "path": "first.csv",
        "bytes": (bundle / "first.csv").stat().st_size,
        "sha256": sha256_file(bundle / "first.csv"),
    }

    loaded = load_figure_manifest(bundle, expected_experiment_id="E4")
    assert loaded["experiment_id"] == "E4"
    assert loaded["figures"][0]["files"]["png"]["resolved_path"] == str(
        (bundle / "first.png").resolve()
    )


@pytest.mark.parametrize(
    "unsafe_path",
    ["../outside.csv", "C:/outside.csv", "/outside.csv", r"nested\outside.csv"],
)
def test_writer_rejects_nonlocal_or_nonposix_paths(tmp_path: Path, unsafe_path: str) -> None:
    bundle = tmp_path / "E4"
    bundle.mkdir()
    files = _assets(bundle)
    files["data"] = unsafe_path
    with pytest.raises(FigureManifestError):
        write_figure_manifest(
            bundle,
            experiment_id="E4",
            evidence_tier="formal_model",
            figures=[_figure(files)],
        )


def test_writer_and_loader_reject_symbolic_links(tmp_path: Path) -> None:
    bundle = tmp_path / "E4"
    bundle.mkdir()
    files = _assets(bundle)
    outside = tmp_path / "outside.csv"
    outside.write_text("x,y\n3,4\n", encoding="utf-8")
    link = bundle / "linked.csv"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    files["data"] = "linked.csv"
    with pytest.raises(FigureManifestError, match="symbolic link|junction"):
        write_figure_manifest(
            bundle,
            experiment_id="E4",
            evidence_tier="formal_model",
            figures=[_figure(files)],
        )

    link.unlink()
    (bundle / "linked.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    files["data"] = "linked.csv"
    manifest = write_figure_manifest(
        bundle,
        experiment_id="E4",
        evidence_tier="formal_model",
        figures=[_figure(files)],
    )
    (bundle / "linked.csv").unlink()
    os.symlink(outside, bundle / "linked.csv")
    with pytest.raises(FigureManifestError, match="symbolic link|junction"):
        load_figure_manifest(manifest)


@pytest.mark.parametrize("drift", ["bytes", "sha256"])
def test_loader_rejects_size_and_hash_drift(tmp_path: Path, drift: str) -> None:
    bundle = tmp_path / "E15"
    bundle.mkdir()
    files = _assets(bundle)
    manifest_path = write_figure_manifest(
        bundle,
        experiment_id="E15",
        evidence_tier="formal_model",
        figures=[_figure(files)],
    )
    png = bundle / "figure.png"
    if drift == "bytes":
        png.write_bytes(png.read_bytes() + b"more")
    else:
        original = png.read_bytes()
        png.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(FigureManifestError, match="byte-size mismatch|SHA-256 mismatch"):
        load_figure_manifest(manifest_path)


def test_loader_rejects_manifest_schema_and_experiment_mismatch(tmp_path: Path) -> None:
    bundle = tmp_path / "E4"
    bundle.mkdir()
    manifest_path = write_figure_manifest(
        bundle,
        experiment_id="E4",
        evidence_tier="formal_model",
        figures=[_figure(_assets(bundle))],
    )
    with pytest.raises(FigureManifestError, match="experiment mismatch"):
        load_figure_manifest(manifest_path, expected_experiment_id="E15")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(FigureManifestError, match="keys mismatch"):
        load_figure_manifest(manifest_path)
