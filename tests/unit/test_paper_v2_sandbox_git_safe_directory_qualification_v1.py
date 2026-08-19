from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import sandbox_git_safe_directory_qualification_v1 as gate


def test_process_scoped_git_qualification_is_non_mutating_and_non_authorizing() -> None:
    value = gate.verify_qualification()

    assert value["status"] == "qualified_process_scoped_safe_directory"
    assert value["safe_observation"]["observed_commit"] == gate.EXPECTED_COMMIT
    assert value["unsafe_observation"]["dubious_ownership_marker_present"] is True
    assert value["unsafe_observation"]["raw_stderr_persisted"] is False
    assert value["remediation"]["scope"] == "process_only"
    assert value["remediation"]["global_git_config_mutated"] is False
    assert value["evidence_boundary"]["provider_calls"] == 0
    assert value["evidence_boundary"]["provider_execution_authorized"] is False


def test_git_qualification_tamper_fails_closed() -> None:
    value = copy.deepcopy(gate.verify_qualification())
    value["remediation"]["global_git_config_mutated"] = True

    with pytest.raises(
        gate.SandboxGitSafeDirectoryQualificationV1Error,
        match="manifest drift",
    ):
        gate.validate_qualification(value)
