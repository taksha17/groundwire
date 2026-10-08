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
    auth_enabled: bool = False
    oidc_issuer: str = "http://localhost:8081/realms/groundwire"
    oidc_jwks_url: str = ""
    oidc_audience: str = "groundwire-api"
    oidc_public_key: str = ""
    router_url: str = ""
    approval_webhook_url: str = ""
    approval_webhook_secret: str = ""
    approval_timeout_hours: float = 72
    tool_executor_url: str = ""
    tool_executor_secret: str = ""
    dashboard_public_url: str = "http://localhost:4200"


def get_settings() -> Settings:
    return Settings()
