"""Learned routing for Mira executive requests."""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from functools import lru_cache

from mira.training.train_intent_router import (
    MODEL_PATH,
    MODEL_VERSION,
    train_model,
)

MIN_CONFIDENCE = 0.35


@dataclass(frozen=True, slots=True)
class IntentPrediction:
    intent: str
    confidence: float
    model_version: str
    low_confidence: bool = False


def ensure_model() -> None:
    if not MODEL_PATH.exists():
        train_model(save=True)


@lru_cache(maxsize=1)
def _load_model() -> dict:
    ensure_model()

    with MODEL_PATH.open("rb") as handle:
        artifact = pickle.load(handle)

    if artifact.get("version") != MODEL_VERSION:
        train_model(save=True)

        with MODEL_PATH.open("rb") as handle:
            artifact = pickle.load(handle)

    return artifact


def predict_intent(text: str) -> IntentPrediction:
    request = text.strip()

    if not request:
        return IntentPrediction(
            intent="help",
            confidence=1.0,
            model_version=MODEL_VERSION,
        )

    artifact = _load_model()
    model = artifact["model"]

    probabilities = model.predict_proba([request])[0]
    classes = model.classes_

    best_index = int(probabilities.argmax())
    confidence = float(probabilities[best_index])

    if confidence < MIN_CONFIDENCE:
        return IntentPrediction(
            intent="unknown",
            confidence=confidence,
            model_version=artifact["version"],
            low_confidence=True,
        )

    return IntentPrediction(
        intent=str(classes[best_index]),
        confidence=confidence,
        model_version=artifact["version"],
    )
