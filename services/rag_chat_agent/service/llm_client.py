"""Simple LLM client supporting OpenAI and Anthropic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)

Provider = Literal["openai", "anthropic"]


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int


def _detect_provider(model: str) -> Provider:
    """Map a model string to a provider."""
    if model.startswith("claude"):
        return "anthropic"
    return "openai"


class LLMClient:
    """Thin wrapper around OpenAI and Anthropic chat completion APIs."""

    def __init__(self) -> None:
        """Initialise available clients based on configured API keys."""
        self._openai: Any | None = None
        self._anthropic: Any | None = None

        if settings.openai_api_key:
            import openai

            self._openai = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        if settings.anthropic_api_key:
            import anthropic

            self._anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Call the configured LLM and return the response.

        Args:
            messages: Chat messages in OpenAI format.
            model: Model name. Defaults to settings.default_llm_model.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.

        Returns:
            LLMResponse with generated text and token counts.
        """
        model = model or settings.default_llm_model
        provider = _detect_provider(model)

        if provider == "anthropic":
            if self._anthropic is None:
                raise RuntimeError("Anthropic API key not configured")
            return await self._anthropic_complete(messages, model, temperature, max_tokens)

        if self._openai is None:
            raise RuntimeError("OpenAI API key not configured")
        return await self._openai_complete(messages, model, temperature, max_tokens)

    async def _openai_complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        import openai

        try:
            response = await self._openai.chat.completions.create(  # type: ignore[union-attr]
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except openai.OpenAIError as exc:
            logger.error("openai_completion_failed", extra={"error": str(exc)})
            raise

        choice = response.choices[0]
        return LLMResponse(
            text=choice.message.content or "",
            model=model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

    async def _anthropic_complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        import anthropic

        system = ""
        conversation = messages
        if messages and messages[0]["role"] == "system":
            system = messages[0]["content"]
            conversation = messages[1:]

        try:
            response = await self._anthropic.messages.create(  # type: ignore[union-attr]
                model=model,
                system=system,
                messages=conversation,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except anthropic.AnthropicError as exc:
            logger.error("anthropic_completion_failed", extra={"error": str(exc)})
            raise

        return LLMResponse(
            text=response.content[0].text if response.content else "",
            model=model,
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
        )
