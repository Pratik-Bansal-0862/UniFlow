from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "UniFlow API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # LLM configuration: secrets stay on the backend.
    llm_provider: str = "groq"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b-16k"
    llm_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
