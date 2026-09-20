"""Isolated SpaceXAI external signals. Does not affect finance truth."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.deps import get_actor
from mira.agents.auth import CanonicalActor
from mira.integrations.spacexai import GrokVoiceAdapter, fetch_space_signals

router = APIRouter(prefix="/api/v1/external-signals", tags=["external-signals"])


class SpaceSpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source: str = Field(pattern="^space_narration$")


@router.get("/space")
def space_signals() -> dict:
    settings = get_settings()
    observations = fetch_space_signals()
    grok = GrokVoiceAdapter(settings.grok_key)
    narration = grok.narrate(observations)
    return {
        **observations,
        "narration": narration,
        "grok": grok.status().value,
        "voice_available": grok.status().value == "live",
        "affects_finance_truth": False,
    }


@router.post("/space/speak")
def speak_space_narration(
    body: SpaceSpeakIn,
    _actor: CanonicalActor = Depends(get_actor),
) -> Response:
    settings = get_settings()
    grok = GrokVoiceAdapter(settings.grok_key)
    if grok.status().value != "live":
        raise HTTPException(status_code=503, detail="Grok Voice is not configured.")
    audio = grok.speak(body.text)
    if not audio:
        raise HTTPException(status_code=503, detail="Grok Voice audio is unavailable.")
    return Response(content=audio, media_type="audio/mpeg")
