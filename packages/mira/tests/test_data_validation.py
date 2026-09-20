from __future__ import annotations

from decimal import Decimal

from mira.agents.runtime import (
    command_center_briefing_data,
    executive_request,
)
from mira.agents.tools import (
    tool_calculate_finance_metrics,
    tool_get_cash_position,
)
from mira.core.models import Company, Decision
from mira.finance.snapshot import load_snapshot


def _snapshot(seeded_session, as_of):
    company = seeded_session.query(Company).first()
    assert company is not None

    return load_snapshot(
        seeded_session,
        company.id,
        as_of,
    )


def test_cash_question_matches_canonical_finance_data(
    seeded_session,
    as_of,
) -> None:
    snapshot = _snapshot(
        seeded_session,
        as_of,
    )

    expected = tool_get_cash_position(snapshot)

    result = executive_request(
        seeded_session,
        snapshot,
        "How much cash do we have?",
    )

    assert result["kind"] == "cash_position"
    assert result["routing"]["intent"] == "cash_position"

    actual = result["artifact"]["cash"]

    assert Decimal(actual["cash"]["amount"]) == Decimal(
        expected.cash.amount
    )

    assert Decimal(actual["open_ap"]["amount"]) == Decimal(
        expected.open_ap.amount
    )

    assert Decimal(actual["open_ar"]["amount"]) == Decimal(
        expected.open_ar.amount
    )


def test_ap_ar_question_matches_canonical_finance_data(
    seeded_session,
    as_of,
) -> None:
    snapshot = _snapshot(
        seeded_session,
        as_of,
    )

    expected = tool_get_cash_position(snapshot)

    result = executive_request(
        seeded_session,
        snapshot,
        "What do customers owe us?",
    )

    assert result["kind"] == "ap_ar"
    assert result["routing"]["intent"] == "ap_ar"

    actual = result["artifact"]["cash"]

    assert Decimal(actual["open_ap"]["amount"]) == Decimal(
        expected.open_ap.amount
    )

    assert Decimal(actual["open_ar"]["amount"]) == Decimal(
        expected.open_ar.amount
    )


def test_pending_approval_answer_matches_database(
    seeded_session,
    as_of,
) -> None:
    snapshot = _snapshot(
        seeded_session,
        as_of,
    )

    expected = (
        seeded_session.query(Decision)
        .filter(
            Decision.company_id == snapshot.company_id,
            Decision.requires_human_approval.is_(True),
            Decision.status.in_(
                {
                    "awaiting_human",
                    "proposed",
                }
            ),
        )
        .all()
    )

    result = executive_request(
        seeded_session,
        snapshot,
        "What payments need my approval?",
    )

    assert result["kind"] == "pending_approvals"
    assert result["routing"]["intent"] == "pending_approvals"

    actual = result["artifact"]["pending"]

    assert len(actual) == len(expected)

    expected_ids = {
        str(row.id)
        for row in expected
    }

    actual_ids = {
        row["id"]
        for row in actual
    }

    assert actual_ids == expected_ids


def test_finance_review_matches_runtime_savings_and_cash(
    seeded_session,
    as_of,
) -> None:
    snapshot = _snapshot(
        seeded_session,
        as_of,
    )

    expected_cash = tool_get_cash_position(snapshot)

    runtime_savings = [
        row
        for row in snapshot.savings
        if row.source == "runtime"
    ]

    expected_protected = sum(
        (
            row.amount_usd
            for row in runtime_savings
            if row.category
            in {
                "duplicate_prevented",
                "policy_block",
            }
        ),
        Decimal("0.00"),
    )

    expected_hours = sum(
        (
            row.hours_saved
            for row in runtime_savings
        ),
        Decimal("0.00"),
    )

    expected_pending = (
        seeded_session.query(Decision)
        .filter(
            Decision.company_id == snapshot.company_id,
            Decision.requires_human_approval.is_(True),
            Decision.status.in_(
                {
                    "awaiting_human",
                    "proposed",
                }
            ),
        )
        .count()
    )

    result = executive_request(
        seeded_session,
        snapshot,
        "What did you catch overnight?",
    )

    assert result["kind"] == "finance_review"

    artifact = result["artifact"]

    assert Decimal(
        artifact["cash"]["cash"]["amount"]
    ) == Decimal(expected_cash.cash.amount)

    assert Decimal(
        artifact["cash"]["open_ap"]["amount"]
    ) == Decimal(expected_cash.open_ap.amount)

    assert Decimal(
        artifact["cash"]["open_ar"]["amount"]
    ) == Decimal(expected_cash.open_ar.amount)

    assert Decimal(
        artifact["dollars_protected"]
    ) == expected_protected

    assert Decimal(
        artifact["hours_returned"]
    ) == expected_hours

    assert artifact["pending_approvals"] == expected_pending

    assert artifact["read_only"] is True


def test_command_center_matches_same_underlying_finance_data(
    seeded_session,
    as_of,
) -> None:
    snapshot = _snapshot(
        seeded_session,
        as_of,
    )

    expected_cash = tool_get_cash_position(snapshot)
    expected_metrics = tool_calculate_finance_metrics(
        snapshot,
        runtime_only=True,
    )

    briefing = command_center_briefing_data(
        seeded_session,
        snapshot,
    )

    assert Decimal(
        briefing["cash"].cash.amount
    ) == Decimal(expected_cash.cash.amount)

    assert Decimal(
        briefing["cash"].open_ap.amount
    ) == Decimal(expected_cash.open_ap.amount)

    assert Decimal(
        briefing["cash"].open_ar.amount
    ) == Decimal(expected_cash.open_ar.amount)

    assert (
        briefing["metrics"].reconciliation_rate
        == expected_metrics.reconciliation_rate
    )

    assert (
        briefing["metrics"].autonomous_completion_rate
        == expected_metrics.autonomous_completion_rate
    )


def test_command_center_and_ask_mira_share_same_cash_truth(
    seeded_session,
    as_of,
) -> None:
    snapshot = _snapshot(
        seeded_session,
        as_of,
    )

    briefing = command_center_briefing_data(
        seeded_session,
        snapshot,
    )

    answer = executive_request(
        seeded_session,
        snapshot,
        "How much cash do we have?",
    )

    ask_cash = Decimal(
        answer["artifact"]["cash"]["cash"]["amount"]
    )

    command_cash = Decimal(
        briefing["cash"].cash.amount
    )

    assert ask_cash == command_cash
