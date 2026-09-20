from __future__ import annotations

import pytest

import mira.agents.runtime as runtime
from mira.agents.runtime import executive_request
from mira.core.models import Company
from mira.finance.snapshot import load_snapshot


def snapshot_for(seeded_session, as_of):
    company = seeded_session.query(Company).first()

    assert company is not None

    return load_snapshot(
        seeded_session,
        company.id,
        as_of,
    )


@pytest.mark.parametrize(
    ("question", "expected_kind"),
    [
        ("How much money do we have?", "cash_position"),
        ("What do customers owe us?", "ap_ar"),
        ("What payments need my approval?", "pending_approvals"),
        ("What did you catch overnight?", "finance_review"),
        ("What can Mira help me with?", "help"),
        ("Should I order pizza tonight?", "unknown"),
    ],
)
def test_executive_request_routes_to_distinct_grounded_work(
    seeded_session,
    as_of,
    question: str,
    expected_kind: str,
) -> None:
    snapshot = snapshot_for(
        seeded_session,
        as_of,
    )

    result = executive_request(
        seeded_session,
        snapshot,
        question,
    )

    assert result["kind"] == expected_kind
    assert result["routing"]["intent"] == expected_kind

    recommendation = result["recommendation"]

    assert recommendation["headline"]
    assert recommendation["body"]

    rendered = (
        recommendation["headline"]
        + " "
        + recommendation["body"]
    )

    assert "source=seed" not in rendered
    assert "Queue is Decision rows" not in rendered


def test_cash_answer_uses_canonical_cash_artifact(
    seeded_session,
    as_of,
) -> None:
    snapshot = snapshot_for(
        seeded_session,
        as_of,
    )

    result = executive_request(
        seeded_session,
        snapshot,
        "How much cash do we have?",
    )

    assert result["kind"] == "cash_position"
    assert "cash" in result["artifact"]

    cash = result["artifact"]["cash"]

    assert cash["cash"]["amount"]
    assert cash["open_ap"]["amount"]
    assert cash["open_ar"]["amount"]


def test_different_questions_do_not_return_same_answer(
    seeded_session,
    as_of,
) -> None:
    snapshot = snapshot_for(
        seeded_session,
        as_of,
    )

    questions = [
        "How much cash do we have?",
        "What do customers owe us?",
        "What payments need my approval?",
        "What did you catch overnight?",
        "What can Mira do?",
    ]

    answers = []

    for question in questions:
        result = executive_request(
            seeded_session,
            snapshot,
            question,
        )

        recommendation = result["recommendation"]

        answers.append(
            (
                recommendation["headline"],
                recommendation["body"],
            )
        )

    assert len(set(answers)) == len(answers)


def test_executive_question_never_runs_overnight_workflow(
    seeded_session,
    as_of,
    monkeypatch,
) -> None:
    snapshot = snapshot_for(
        seeded_session,
        as_of,
    )

    def explode(*args, **kwargs):
        raise AssertionError(
            "executive_request must not invoke overnight_review"
        )

    monkeypatch.setattr(
        runtime,
        "overnight_review",
        explode,
    )

    result = executive_request(
        seeded_session,
        snapshot,
        "What did you catch overnight?",
    )

    assert result["kind"] == "finance_review"


def test_unknown_request_does_not_fake_finance_answer(
    seeded_session,
    as_of,
) -> None:
    snapshot = snapshot_for(
        seeded_session,
        as_of,
    )

    result = executive_request(
        seeded_session,
        snapshot,
        "Should I order pizza tonight?",
    )

    assert result["kind"] == "unknown"
    assert result["routing"]["low_confidence"] is True

    body = result["recommendation"]["body"].lower()

    assert "cash is" not in body
    assert "open ap" not in body
    assert "overnight" not in body
