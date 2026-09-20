from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from mira.agents.protocol import MIRA_ORG
from mira.integrations.deepgram import DeepgramAdapter
from mira.integrations.dropbox import StorageAdapter
from mira.integrations.elastic import ElasticAdapter
from mira.integrations.elevenlabs import ElevenLabsAdapter
from mira.integrations.public_data import PublicDataAdapter
from mira.integrations.spacexai import GrokVoiceAdapter
from mira.integrations.visa import VisaAdapter
from mira.integrations.zenni import SKILL_ROUTES, ZenniAdapter

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/meta")
def meta() -> dict:
    settings = get_settings()

    adapters = [
        StorageAdapter(settings.dropbox_access_token),
        ElasticAdapter(
            settings.elasticsearch_url,
            api_key=settings.elasticsearch_api_key,
        ),
        DeepgramAdapter(settings.deepgram_api_key),
        ElevenLabsAdapter(settings.elevenlabs_api_key, voice_id=settings.elevenlabs_voice_id),
        VisaAdapter(),
        ZenniAdapter(),
        PublicDataAdapter(),
        GrokVoiceAdapter(settings.grok_key),
    ]
    return {
        "product": "Mira",
        "thesis": "Autonomous digital CFO — one employee, not a chatbot.",
        "agents_implemented": True,
        "org": [
            {
                "role": spec.role.value,
                "title": spec.title,
                "speaks_to_user": spec.speaks_to_user,
            }
            for spec in MIRA_ORG
        ],
        "adapters": {a.name: a.status().value for a in adapters},
        "zenni_skill_routes": list(SKILL_ROUTES),
        "sandbox_notice": "Visa and bank actions in this demo are sandbox/simulated.",
    }
