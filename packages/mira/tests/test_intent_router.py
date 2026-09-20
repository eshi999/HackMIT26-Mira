from __future__ import annotations

import pytest

from mira.agents.intent_router import MIN_CONFIDENCE, predict_intent


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("How much cash do we have?", "cash_position"),
        ("What do customers owe us?", "ap_ar"),
        ("What payments need my approval?", "pending_approvals"),
        ("Are we ready to close September?", "close_status"),
        ("Can we afford another engineer?", "scenario"),
        ("Why did AWS spend increase?", "vendor_spend"),
        ("Why was the HelixCloud invoice held?", "invoice_investigation"),
        ("Where did this number come from?", "evidence_query"),
        ("What did you catch overnight?", "finance_review"),
        ("What controls failed?", "risk_controls"),
        ("What can you do?", "help"),
    ],
)
def test_core_cfo_intents(question: str, expected: str) -> None:
    result = predict_intent(question)

    assert result.intent == expected
    assert 0.0 <= result.confidence <= 1.0
    assert result.model_version


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("How much money is available right now?", "cash_position"),
        ("How much are customers still supposed to pay us?", "ap_ar"),
        ("Are any payments waiting on me?", "pending_approvals"),
        ("Which transactions need approval?", "pending_approvals"),
        ("What happened with HelixCloud?", "invoice_investigation"),
        ("Why was that vendor bill stopped?", "invoice_investigation"),
        ("How far are we from finishing September close?", "close_status"),
        ("What's holding up month end?", "close_status"),
        ("Why are our cloud costs up?", "vendor_spend"),
        ("What's driving the AWS bill?", "vendor_spend"),
        ("Can we hire two more developers?", "scenario"),
        ("What does another employee do to runway?", "scenario"),
        ("Show me what supports that decision", "evidence_query"),
        ("Where did that information come from?", "evidence_query"),
        ("What risks should I know about?", "risk_controls"),
        ("Are there any control failures?", "risk_controls"),
        ("What did Mira find?", "finance_review"),
        ("Give me the overnight findings", "finance_review"),
        ("What can Mira help me with?", "help"),
        ("What sort of questions can I ask?", "help"),
    ],
)
def test_unseen_cfo_paraphrases(question: str, expected: str) -> None:
    result = predict_intent(question)

    assert result.intent == expected


@pytest.mark.parametrize(
    "question",
    [
        "Should I order pizza tonight?",
        "Who won the basketball game?",
        "Write me a poem",
        "What's the weather outside?",
        "Tell me about dinosaurs",
        "Book me a flight",
        "Recommend a movie",
        "How do I bake a cake?",
    ],
)
def test_out_of_domain_requests_are_rejected(question: str) -> None:
    result = predict_intent(question)

    assert result.intent == "unknown"
    assert result.low_confidence is True
    assert result.confidence < MIN_CONFIDENCE


def test_empty_request_routes_to_help() -> None:
    result = predict_intent("")

    assert result.intent == "help"
    assert result.confidence == 1.0


def test_confidence_threshold_is_not_overly_permissive() -> None:
    assert MIN_CONFIDENCE >= 0.35
