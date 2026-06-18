"""OBS-005 — head-based sampling policy tests.

Pure unit tests on KaoriHeadSampler. No OpenTelemetry runtime needed
beyond importing the SamplingResult / Decision shapes.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace.sampling import Decision

from ai_orchestrator.shared.kaori_sampler import (
    DEFAULT_CHATTY_PATHS,
    DEFAULT_HIGH_VALUE_PATHS,
    KaoriHeadSampler,
    build_sampler,
)


def _sampler(*, base=0.0, chatty=0.0, high_value=None, chatty_paths=None,
             force_tenants=frozenset()):
    """Default base=0.0 so non-special paths get DROP — makes intent
    explicit when asserting that high-value paths still sample."""
    return KaoriHeadSampler(
        base_rate=base, chatty_rate=chatty,
        high_value_paths=high_value or DEFAULT_HIGH_VALUE_PATHS,
        chatty_paths=chatty_paths or DEFAULT_CHATTY_PATHS,
        force_sample_tenants=force_tenants,
    )


def _decide(sampler, path, *, tenant_id=None, name="span"):
    attrs = {"http.target": path}
    if tenant_id is not None:
        attrs["tenant_id"] = tenant_id
    return sampler.should_sample(
        parent_context=None, trace_id=12345, name=name, attributes=attrs,
    )


# ─── High-value paths always sample ─────────────────────────────────


class TestHighValuePaths:

    @pytest.mark.parametrize("path", [
        "/decisions",
        "/decisions/abc",
        "/v1/infer",
        "/v1/embed",
        "/workflows/123/run",
        "/process-mining/connectors/gmail-outlook",
        "/economics/reports/manager-digest",
    ])
    def test_high_value_path_sampled_even_when_base_zero(self, path):
        s = _sampler(base=0.0, chatty=0.0)
        result = _decide(s, path)
        assert result.decision == Decision.RECORD_AND_SAMPLE
        assert result.attributes["kaori.sampling.reason"] == "high_value_path"

    def test_unrelated_path_falls_to_base(self):
        s = _sampler(base=0.0)
        result = _decide(s, "/api/v1/random/thing")
        assert result.decision == Decision.DROP
        assert result.attributes["kaori.sampling.reason"] == "base_rate"


# ─── Chatty paths use chatty rate ───────────────────────────────────


class TestChattyPaths:

    @pytest.mark.parametrize("path", ["/health", "/metrics", "/health/ready"])
    def test_chatty_path_uses_chatty_rate(self, path):
        s = _sampler(base=1.0, chatty=0.0)   # chatty rate = 0 → DROP
        result = _decide(s, path)
        assert result.decision == Decision.DROP
        assert result.attributes["kaori.sampling.reason"] == "chatty_downsample"

    def test_chatty_path_sampled_when_chatty_rate_high(self):
        s = _sampler(base=0.0, chatty=1.0)   # chatty rate = 1 → SAMPLE
        result = _decide(s, "/health")
        assert result.decision == Decision.RECORD_AND_SAMPLE


# ─── Force-sample tenants ───────────────────────────────────────────


class TestForceSampleTenants:

    def test_force_sample_overrides_base_drop(self):
        tid = "11111111-1111-1111-1111-111111111111"
        s = _sampler(base=0.0, force_tenants=frozenset({tid}))
        result = _decide(s, "/api/v1/anything", tenant_id=tid)
        assert result.decision == Decision.RECORD_AND_SAMPLE
        assert result.attributes["kaori.sampling.reason"] == "force_sample_tenant"

    def test_non_force_tenant_falls_through(self):
        s = _sampler(
            base=0.0,
            force_tenants=frozenset({"22222222-2222-2222-2222-222222222222"}),
        )
        result = _decide(s, "/api/v1/anything",
                          tenant_id="33333333-3333-3333-3333-333333333333")
        assert result.decision == Decision.DROP


# ─── Default base rate ──────────────────────────────────────────────


class TestBaseRate:

    def test_base_rate_one_always_samples(self):
        s = _sampler(base=1.0)
        result = _decide(s, "/api/v1/foo")
        assert result.decision == Decision.RECORD_AND_SAMPLE
        assert result.attributes["kaori.sampling.reason"] == "base_rate"


# ─── build_sampler factory + env-var parsing ────────────────────────


class TestBuildSampler:

    def test_default_no_env_returns_parent_based(self):
        with patch.dict(os.environ, {}, clear=False):
            for var in ["TRACING_SAMPLE_RATE", "TRACING_CHATTY_RATE",
                         "KAORI_HIGH_VALUE_PATHS", "KAORI_CHATTY_PATHS",
                         "KAORI_FORCE_SAMPLE_TENANTS"]:
                os.environ.pop(var, None)
            sampler = build_sampler()
            desc = sampler.get_description()
            # ParentBased wraps the head sampler
            assert "ParentBased" in desc

    def test_env_overrides_high_value_paths(self):
        with patch.dict(os.environ, {"KAORI_HIGH_VALUE_PATHS": "/custom,/special"}):
            sampler = build_sampler()
            desc = sampler.get_description()
            assert "/custom" in desc
            assert "/special" in desc

    def test_env_force_tenants_parsed(self):
        tid = "11111111-1111-1111-1111-111111111111"
        with patch.dict(os.environ, {"KAORI_FORCE_SAMPLE_TENANTS": f"{tid},extra"}):
            sampler = build_sampler()
            assert "force_sample_tenants_count=2" in sampler.get_description()

    def test_bad_float_env_falls_back_to_default(self):
        with patch.dict(os.environ, {"TRACING_SAMPLE_RATE": "not_a_number"}):
            sampler = build_sampler()
            # No crash + valid sampler
            assert "ParentBased" in sampler.get_description()


# ─── Sampler description ────────────────────────────────────────────


def test_description_shape():
    s = _sampler(base=0.5, chatty=0.01)
    desc = s.get_description()
    assert "base=0.5" in desc
    assert "chatty=0.01" in desc
