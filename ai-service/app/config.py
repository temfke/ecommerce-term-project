import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "stub").lower()

    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash-lite")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    LLM_REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "8"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "0"))

    # Multi-agent SQL self-correction loop. When MySQL rejects the LLM-generated
    # query the error_agent feeds the failure back to the LLM and retries up to
    # MAX_RETRIES times before giving up.
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

    # Per-user in-memory token bucket. Keeps the cost of an abusive client
    # bounded even when an LLM provider has a generous free tier.
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "20"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8001"))

    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")

    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "ecommerce_db")
    DB_USER: str = os.getenv("DB_USER", "chatbot_ro")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_QUERY_TIMEOUT_SECONDS: int = int(os.getenv("DB_QUERY_TIMEOUT_SECONDS", "25"))


settings = Settings()
