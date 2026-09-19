from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import company, health, meta, mira
from mira.core.db import create_schema, get_engine, reset_engine
from mira.seed.northstar import seed_from_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        Path("data").mkdir(exist_ok=True)
    reset_engine()
    engine = get_engine(settings.database_url)
    create_schema(engine)
    if settings.mira_bootstrap:
        seed_from_url(settings.database_url)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Mira API",
        description="Autonomous digital CFO — Office of the CFO runtime shell.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.include_router(company.router)
    application.include_router(meta.router)
    application.include_router(mira.router)
    return application


app = create_app()
