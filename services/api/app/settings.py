from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "sqlite:///./data/junyu_mvp.sqlite3"
    enable_scheduler: bool = True
    data_sync_cron: str = "5 0 * * *"
    app_timezone: str = "Asia/Shanghai"
    event_pacing_seconds: float = 7.0

    model_provider: str = "deepseek"
    model_name: str = "deepseek-v4-pro"
    deepseek_api_key: str | None = Field(default=None, repr=False)
    enable_llm_dialogue: bool = False
    enable_llm_refinement: bool = False

    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001"
    )

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def demo_mode(self) -> bool:
        return not bool(self.deepseek_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
