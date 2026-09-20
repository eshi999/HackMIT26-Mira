from __future__ import annotations

import inspect

from mira.integrations.spacexai import _script_from_observations, fetch_space_signals


def test_spacexai_module_does_not_touch_finance() -> None:
    from mira.integrations import spacexai

    source = inspect.getsource(spacexai)
    assert "FinanceSnapshot" not in source
    assert "SavingsEvent" not in source
    assert "executive_request" not in source


def test_offline_space_signals_are_labeled(monkeypatch) -> None:
    monkeypatch.setenv("MIRA_SPACE_OFFLINE", "1")
    payload = fetch_space_signals()
    assert payload["isolated"] is True
    assert payload["affects_finance_truth"] is False
    assert payload["live"] is False
    assert payload["launch"]["provider"] == "demo_snapshot"
    script = _script_from_observations(payload)
    assert "finance" not in script.lower()
    assert "invoice" not in script.lower()
