from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения. Загружаются из переменных окружения."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # API
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Auth
    MASTER_TOKEN: str = ""

    # LLM Provider
    OPENROUTER_API_KEY: str = ""

    # Guardrails
    GUARDRAILS_ENABLED: bool = True

    # Langfuse
    LANGFUSE_HOST: str = "http://langfuse:3000"
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""


settings = Settings()
