from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/mira.db"
    mira_env: str = "development"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    mira_bootstrap: bool = True
    openai_api_key: str | None = None
    deepgram_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    dropbox_access_token: str | None = None
    elasticsearch_url: str | None = None
    elasticsearch_api_key: str | None = None
    zenni_skill_token: str | None = None
    xai_api_key: str | None = None
    grok_api_key: str | None = None
    visa_sandbox: bool = True

    @property
    def grok_key(self) -> str | None:
        return self.xai_api_key or self.grok_api_key

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()
