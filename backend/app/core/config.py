from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Forja Studio"
    environment: str = "production"
    secret_key: str = Field(default="change-me", min_length=8)
    access_token_expire_minutes: int = 720
    media_url_expire_seconds: int = 6 * 3600
    allow_registration: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    database_url: str = "postgresql+psycopg://forja:forja@localhost:5432/forja"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_task_always_eager: bool = False

    admin_email: str | None = None
    admin_password: str | None = None
    admin_name: str = "Administrador"

    storage_dir: Path = BASE_DIR / "data" / "storage"
    temp_dir: Path = BASE_DIR / "data" / "tmp"
    models_dir: Path = BASE_DIR / "data" / "models"
    fonts_dir: Path = BASE_DIR / "assets" / "fonts"
    use_x_accel: bool = False
    x_accel_prefix: str = "/protected-media"

    max_image_upload_mb: int = 15
    max_audio_upload_mb: int = 40
    user_quota_mb: int = 5120

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    llm_provider: str = "ollama"
    llm_timeout_seconds: int = 300

    image_provider: str = "procedural"
    comfyui_url: str = "http://localhost:8188"
    comfyui_checkpoint: str = "sd_xl_base_1.0.safetensors"
    comfyui_timeout_seconds: int = 600

    tts_provider: str = "kokoro"
    kokoro_model_file: str = "kokoro/kokoro-v1.0.int8.onnx"
    kokoro_voices_file: str = "kokoro/voices-v1.0.bin"
    piper_voice_male: str = "piper/pt_BR-faber-medium.onnx"

    render_max_retries: int = 2
    render_soft_time_limit: int = 3600
    login_max_attempts: int = 8
    login_window_seconds: int = 900

    @property
    def broker(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    for d in (s.storage_dir, s.temp_dir, s.models_dir):
        d.mkdir(parents=True, exist_ok=True)
    return s
