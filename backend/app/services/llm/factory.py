"""
Cartographer — LLM Provider Factory.

Single entry point for resolving the configured LLM provider.
Business logic calls get_llm_provider() and receives an LLMProvider
without knowing which concrete class backs it.

Provider selection is driven entirely by the LLM_PROVIDER env var.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings
from app.core.exceptions import ProviderConfigurationError

if TYPE_CHECKING:
    from app.services.llm.base import LLMProvider

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """
    Resolve and return the configured LLM provider singleton.

    The provider is determined by LLM_PROVIDER environment variable:
      - "anthropic" → AnthropicProvider (Claude)
      - "openai"    → OpenAIProvider (GPT-4.1 / compatible APIs)
      - "ollama"    → OllamaProvider (local, requires OLLAMA_ENABLED=true)

    Returns:
        Concrete LLMProvider implementation.

    Raises:
        ProviderConfigurationError: If the provider is unknown or misconfigured.
    """
    settings = get_settings()
    provider_name = settings.llm_provider

    logger.info("llm.factory.resolving", provider=provider_name, model=settings.llm_model)

    match provider_name:
        case "anthropic":
            if not settings.anthropic_api_key:
                raise ProviderConfigurationError(
                    "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
                )
            from app.services.llm.providers.anthropic_provider import (
                AnthropicProvider,  # noqa: PLC0415
            )

            return AnthropicProvider()

        case "openai":
            if not settings.openai_api_key:
                raise ProviderConfigurationError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
                )
            from app.services.llm.providers.openai_provider import OpenAIProvider  # noqa: PLC0415

            return OpenAIProvider()

        case "ollama":
            if not settings.ollama_enabled:
                raise ProviderConfigurationError(
                    "Set OLLAMA_ENABLED=true to use the Ollama provider"
                )
            from app.services.llm.providers.ollama_provider import OllamaProvider  # noqa: PLC0415

            return OllamaProvider()

        case _:
            raise ProviderConfigurationError(
                f"Unknown LLM provider: '{provider_name}'. Valid values: anthropic, openai, ollama"
            )
