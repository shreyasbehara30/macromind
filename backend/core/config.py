from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file, not the process working directory.
# Launching from the repo root instead of backend/ used to silently skip .env
# and fall back to the defaults below.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """Application settings.

    Secrets have no defaults on purpose. They come from backend/.env, which is
    gitignored. An empty value means "not configured" and the dependent feature
    should fail loudly rather than run on a credential baked into source.
    """

    # LLM Settings
    GROQ_API_KEY: str = ""
    # Groq retires model IDs without notice (llama-3.3-70b-versatile died
    # this way). The ID lives here, not hardcoded at call sites.
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER_PRIMARY: str = "groq"
    LLM_PROVIDER_FALLBACK: str = "groq"
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen:4b"

    # Market Data API Keys
    ALPHA_VANTAGE_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""
    COINGECKO_API_KEY: str = ""
    NSE_SESSION_REFRESH_INTERVAL: int = 900
    FINNHUB_WEBSOCKET_ENABLED: bool = True
    ANOMALY_THRESHOLD_PERCENT: float = 1.5
    ANOMALY_WINDOW_MINUTES: int = 5
    NEWS_POLL_INTERVAL_HIGH_PRIORITY: int = 300

    # Database and Cache
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

    # Security
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8")


settings = Settings()
