"""LLM provider factory. Falls back to a deterministic stub if no API key is set
so developers can run the service without spending tokens.
"""
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from .config import settings


def get_chat_model() -> Optional[BaseChatModel]:
    provider = settings.LLM_PROVIDER

    if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=0,
            max_tokens=1024,
        )

    if provider == "openai" and settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
            max_tokens=1024,
        )

    # provider == "stub" or missing key → caller must handle None
    return None
