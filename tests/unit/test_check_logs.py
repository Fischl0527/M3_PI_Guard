from __future__ import annotations

from m3_core.check_logs import _safe_mock_endpoint


def test_reserved_example_and_test_hosts_are_explicit_mock_endpoints() -> None:
    assert _safe_mock_endpoint("https://api.example.test/v1/local-fixture")
    assert _safe_mock_endpoint("https://api.example.com/local-fixture")
    assert _safe_mock_endpoint("http://service.invalid/mock")
    assert _safe_mock_endpoint("mock://evidence/check")


def test_public_or_lookalike_hosts_remain_rejected() -> None:
    assert not _safe_mock_endpoint("https://api.production.example.co/v1")
    assert not _safe_mock_endpoint("https://example.com.attacker.test.example.co/v1")
    assert not _safe_mock_endpoint("https://evil-example.com/v1")
