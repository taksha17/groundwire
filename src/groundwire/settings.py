from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://groundwire:groundwire@localhost:5432/groundwire"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "groundwire-agent-runs"
    default_tenant_id: UUID = DEFAULT_TENANT_ID


def get_settings() -> Settings:
    return Settings()
