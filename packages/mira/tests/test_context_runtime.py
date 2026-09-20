from types import SimpleNamespace

from mira.agents import openai_runtime
from mira.agents.tools import collect_aws_spend_evidence
from mira.finance.snapshot import load_snapshot
from mira.seed import ids


def test_runtime_context_fallback_without_openai(seeded_session, as_of, monkeypatch):
    snapshot = load_snapshot(seeded_session, ids.COMPANY, as_of)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CONTEXT_OPTIMIZATION", "on")
    result = openai_runtime.run_aws_spend_investigation(snapshot, "Why did AWS spend change?")
    assert result["execution"] == "deterministic_fallback"
    assert not result["model_invoked"]
    assert result["evidence"] == collect_aws_spend_evidence(snapshot, "2026-09")
    assert result["context_usage"]["usage_source"] == "estimated"
    assert result["context_budget"]["mode"] == "on"


def test_runner_receives_budgeted_context_and_configured_model(seeded_session, as_of, monkeypatch):
    snapshot = load_snapshot(seeded_session, ids.COMPANY, as_of)
    monkeypatch.setenv("CONTEXT_OPTIMIZATION", "on")
    monkeypatch.setenv("MIRA_MODEL_HIGH_REASONING", "configured-model")

    # Preserve the real installed SDK tools; this runner examines the actual
    # input/Agent contract without pretending FunctionTool is a Python function.
    class Runner:
        @staticmethod
        def run_sync(agent, prompt):
            assert '"profile":"CFO_VARIANCE_INVESTIGATION"' in prompt
            assert '"period_total":"19800.00"' in prompt
            assert '"prior_total":"11000.00"' in prompt
            assert "Unrelated company history" not in prompt
            if openai_runtime.Agent is not None:
                assert agent.model == "configured-model"
            assert agent.tools
            return SimpleNamespace(
                final_output="Explained tool evidence",
                context_wrapper=SimpleNamespace(
                    usage=SimpleNamespace(input_tokens=2000, output_tokens=30)
                ),
            )

    result = openai_runtime.run_aws_spend_investigation(
        snapshot, "Explain AWS", runner=Runner, force_live=True
    )
    assert result["execution"] == "openai_agents_sdk"
    assert result["context_usage"]["usage_source"] == "estimated"
    assert result["provider_usage"]["usage_source"] == "provider_reported"
    assert result["provider_usage"]["input_tokens"] == 2000
    assert result["evidence"] == collect_aws_spend_evidence(snapshot, "2026-09")


def test_provider_failure_retains_deterministic_fallback(seeded_session, as_of, monkeypatch):
    snapshot = load_snapshot(seeded_session, ids.COMPANY, as_of)
    monkeypatch.setenv("CONTEXT_OPTIMIZATION", "on")

    class Runner:
        @staticmethod
        def run_sync(agent, prompt):
            raise RuntimeError("provider offline")

    result = openai_runtime.run_aws_spend_investigation(
        snapshot, "Explain AWS", runner=Runner, force_live=True
    )
    assert result["execution"] == "deterministic_fallback"
    assert result["evidence"] == collect_aws_spend_evidence(snapshot, "2026-09")
