from __future__ import annotations

from collections import Counter

from sklearn.model_selection import StratifiedKFold, cross_val_score

from mira.training.train_intent_router import (
    MODEL_PATH,
    build_model,
    load_examples,
    train_model,
)


EXPECTED_INTENTS = {
    "cash_position",
    "ap_ar",
    "pending_approvals",
    "close_status",
    "scenario",
    "vendor_spend",
    "invoice_investigation",
    "evidence_query",
    "finance_review",
    "risk_controls",
    "help",
}

# Small domain classifier:
# behavioral regression tests are the primary gate.
# Cross-validation protects against broad model-quality regressions.
MIN_MEAN_CV_ACCURACY = 0.80
MIN_WORST_FOLD_ACCURACY = 0.65
MIN_EXAMPLES_PER_INTENT = 8


def test_training_dataset_has_expected_intents() -> None:
    _, labels = load_examples()

    assert set(labels) == EXPECTED_INTENTS


def test_every_intent_has_enough_training_examples() -> None:
    _, labels = load_examples()

    counts = Counter(labels)

    for intent in EXPECTED_INTENTS:
        assert counts[intent] >= MIN_EXAMPLES_PER_INTENT, (
            f"{intent} only has {counts[intent]} training examples"
        )


def test_cross_validated_accuracy_remains_healthy() -> None:
    texts, labels = load_examples()

    model = build_model()

    cv = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=42,
    )

    scores = cross_val_score(
        model,
        texts,
        labels,
        cv=cv,
        scoring="accuracy",
    )

    mean_accuracy = float(scores.mean())
    worst_fold = float(scores.min())

    print()
    print(
        "Intent CV scores:",
        ", ".join(f"{score:.3f}" for score in scores),
    )
    print(f"Mean CV accuracy: {mean_accuracy:.3f}")
    print(f"Worst fold: {worst_fold:.3f}")

    assert mean_accuracy >= MIN_MEAN_CV_ACCURACY, (
        f"Mean cross-validation accuracy fell to "
        f"{mean_accuracy:.3f}"
    )

    assert worst_fold >= MIN_WORST_FOLD_ACCURACY, (
        f"Worst cross-validation fold fell to "
        f"{worst_fold:.3f}"
    )


def test_production_model_is_trained_on_full_dataset() -> None:
    texts, _ = load_examples()

    result = train_model(save=False)

    assert result["training_examples"] == len(texts)


def test_generated_model_exists_after_training() -> None:
    if not MODEL_PATH.exists():
        train_model(save=True)

    assert MODEL_PATH.exists()
