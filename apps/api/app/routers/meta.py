from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from mira.agents.protocol import MIRA_ORG
from mira.integrations.deepgram import DeepgramAdapter
from mira.integrations.dropbox import StorageAdapter
from mira.integrations.elastic import ElasticAdapter
from mira.integrations.public_data import PublicDataAdapter
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
        DeepgramAdapter(),
        VisaAdapter(),
        ZenniAdapter(),
        PublicDataAdapter(),
    ]
    return {
        "product": "Mira",
        "thesis": "Autonomous digital CFO — one employee, not a chatbot.",
        "agents_implemented": False,
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
