"""Train Mira's executive intent classifier.

The classifier learns language routing only.
Financial values, risk, policy, authority, and evidence remain deterministic.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = ROOT / "data" / "training" / "executive_intents.jsonl"
MODEL_PATH = ROOT / "data" / "models" / "executive_intent_router.pkl"

MODEL_VERSION = "intent-router-v2"


def load_examples() -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []

    for line in DATA_PATH.read_text().splitlines():
        if not line.strip():
            continue

        row = json.loads(line)

        texts.append(str(row["text"]).strip())
        labels.append(str(row["intent"]).strip())

    return texts, labels


def build_model() -> Pipeline:
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                ),
            ),
            (
                "character",
                TfidfVectorizer(
                    analyzer="char_wb",
                    lowercase=True,
                    ngram_range=(3, 5),
                    sublinear_tf=True,
                ),
            ),
        ]
    )

    return Pipeline(
        [
            ("features", features),
            (
                "classifier",
                LogisticRegression(
                    max_iter=3000,
                    class_weight="balanced",
                    random_state=42,
                    C=4.0,
                ),
            ),
        ]
    )


def train_model(*, save: bool = True) -> dict:
    texts, labels = load_examples()

    train_x, test_x, train_y, test_y = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )

    # Evaluation model: train only on the training split.
    evaluation_model = build_model()
    evaluation_model.fit(train_x, train_y)

    predictions = evaluation_model.predict(test_x)

    accuracy = float(
        accuracy_score(
            test_y,
            predictions,
        )
    )

    report = classification_report(
        test_y,
        predictions,
        zero_division=0,
    )

    # Production model: after evaluation, retrain on ALL labeled examples.
    #
    # The previous implementation accidentally persisted the evaluation model,
    # meaning production only learned from 75% of our already-small dataset.
    production_model = build_model()
    production_model.fit(
        texts,
        labels,
    )

    artifact = {
        "version": MODEL_VERSION,
        "accuracy": accuracy,
        "training_examples": len(texts),
        "evaluation_examples": len(test_x),
        "labels": sorted(set(labels)),
        "model": production_model,
    }

    if save:
        MODEL_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with MODEL_PATH.open("wb") as handle:
            pickle.dump(
                artifact,
                handle,
            )

    return {
        **artifact,
        "report": report,
    }


def main() -> None:
    result = train_model(
        save=True,
    )

    print(result["report"])
    print(
        f"Evaluation accuracy: "
        f"{result['accuracy']:.3f}"
    )
    print(
        f"Production training examples: "
        f"{result['training_examples']}"
    )
    print(
        f"Model saved to: "
        f"{MODEL_PATH}"
    )


if __name__ == "__main__":
    main()
