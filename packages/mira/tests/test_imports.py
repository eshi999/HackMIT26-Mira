from __future__ import annotations

from mira import __version__
from mira.agents.protocol import MIRA_ORG
from mira.core.models import CANONICAL_MODELS
from mira.integrations import AdapterStatus


def test_package_imports() -> None:
    assert __version__ == "0.1.0"
    assert len(CANONICAL_MODELS) >= 25
    assert any(spec.speaks_to_user for spec in MIRA_ORG)
    assert AdapterStatus.DEMO.value == "demo"
