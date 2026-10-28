from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    """Configuration centralisée (variables d'env ou fichier .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "FlowForge AI"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Providers LLM -------------------------------------------------
    default_provider: str = "mock"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    vertex_api_key: str | None = None
    vertex_project: str | None = None
    vertex_location: str = "us-central1"
    ollama_base_url: str = "http://localhost:11434"
    vllm_base_url: str = "http://localhost:8000/v1"

    # --- Embeddings ----------------------------------------------------
    embedding_provider: str = "mock"  # mock | openai
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 256

    # --- Connecteurs ---------------------------------------------------
    google_drive_credentials: str | None = None  # chemin vers service_account.json
    confluence_base_url: str | None = None
    confluence_email: str | None = None
    confluence_api_token: str | None = None

    # --- Moteur --------------------------------------------------------
    code_node_timeout: int = 10
    max_parallel_nodes: int = 8
    max_upload_size_mb: int = 100

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
