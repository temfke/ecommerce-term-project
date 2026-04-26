import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "stub").lower()

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8001"))

    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")

    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "ecommerce_db")
    DB_USER: str = os.getenv("DB_USER", "chatbot_ro")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_QUERY_TIMEOUT_SECONDS: int = int(os.getenv("DB_QUERY_TIMEOUT_SECONDS", "10"))


settings = Settings()
