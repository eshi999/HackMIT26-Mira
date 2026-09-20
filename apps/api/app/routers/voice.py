"""Voice: Deepgram STT into the existing executive request; optional ElevenLabs TTS."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_actor, get_db
from mira.agents.auth import CanonicalActor
from mira.agents.runtime import executive_request
from mira.core.models import Company
from mira.finance.snapshot import load_snapshot
from mira.integrations.deepgram import DeepgramAdapter, DeepgramIntegrationError
from mira.integrations.elevenlabs import ElevenLabsAdapter, ElevenLabsIntegrationError
from mira.seed.northstar import AS_OF

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

TYPED_FALLBACK = "Deepgram is unavailable. Type the request instead."


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    source: str = Field(pattern="^mira_result$")


def _company_snapshot(db: Session):
    company = db.query(Company).filter(Company.slug == "northstar-labs").one()
    return company, load_snapshot(db, company.id, AS_OF.date())


@router.get("/status")
def voice_status() -> dict:
    settings = get_settings()

    stt = DeepgramAdapter(settings.deepgram_api_key, timeout=4.0)
    tts = ElevenLabsAdapter(
        settings.elevenlabs_api_key,
        voice_id=settings.elevenlabs_voice_id,
        timeout=4.0,
    )

    try:
        stt_status = stt.health_check().value
    except DeepgramIntegrationError:
        stt_status = "unavailable"

    try:
        tts_status = tts.health_check().value
    except ElevenLabsIntegrationError:
        tts_status = "unavailable"

    return {
        "stt": stt_status,
        "tts": tts_status,
        "voice_ready": stt_status == "live" and tts_status == "live",
        "typed_fallback": True,
        "tts_generates_finance": False,
    }


@router.post("/transcribe")
def transcribe_audio(
    audio: UploadFile = File(...),
    _actor: CanonicalActor = Depends(get_actor),
) -> dict:
    settings = get_settings()
    adapter = DeepgramAdapter(settings.deepgram_api_key)
    if adapter.status().value != "live":
        raise HTTPException(status_code=503, detail=TYPED_FALLBACK)
    blob = audio.file.read()
    try:
        transcript = adapter.transcribe(blob, audio.content_type)
    except DeepgramIntegrationError as exc:
        raise HTTPException(status_code=503, detail=TYPED_FALLBACK) from exc
    return {
        "transcript": transcript.text,
        "confidence": transcript.confidence,
        "provider": transcript.provider,
        "typed_fallback": False,
    }


@router.post("/request")
def voice_request(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    _actor: CanonicalActor = Depends(get_actor),
) -> dict:
    settings = get_settings()
    adapter = DeepgramAdapter(settings.deepgram_api_key)
    if adapter.status().value != "live":
        raise HTTPException(status_code=503, detail=TYPED_FALLBACK)
    blob = audio.file.read()
    try:
        transcript = adapter.transcribe(blob, audio.content_type)
    except DeepgramIntegrationError as exc:
        raise HTTPException(status_code=503, detail=TYPED_FALLBACK) from exc
    _company, snapshot = _company_snapshot(db)
    result = executive_request(db, snapshot, transcript.text)
    db.commit()
    tts = ElevenLabsAdapter(settings.elevenlabs_api_key, voice_id=settings.elevenlabs_voice_id)
    return {
        **result,
        "transcript": transcript.text,
        "stt": "deepgram",
        "voice_output_available": tts.status().value == "live",
    }


@router.post("/speak")
def speak_mira_result(
    body: SpeakIn,
    _actor: CanonicalActor = Depends(get_actor),
) -> Response:
    settings = get_settings()
    adapter = ElevenLabsAdapter(settings.elevenlabs_api_key, voice_id=settings.elevenlabs_voice_id)
    if adapter.status().value != "live":
        raise HTTPException(status_code=503, detail="ElevenLabs is not configured.")
    try:
        audio = adapter.speak(body.text)
    except ElevenLabsIntegrationError as exc:
        raise HTTPException(status_code=503, detail="ElevenLabs is unavailable.") from exc
    return Response(content=audio, media_type="audio/mpeg")
