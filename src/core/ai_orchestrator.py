"""AI API Orchestrator with fallback and collaboration support."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings

logger = structlog.get_logger()


class AIProvider(str, Enum):
    """Available AI providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    PERPLEXITY = "perplexity"


class AITaskType(str, Enum):
    """Types of AI tasks with optimal provider mapping."""

    SEARCH = "search"  # Best: Perplexity
    SUMMARIZE = "summarize"  # Best: OpenAI
    ANALYZE = "analyze"  # Best: Claude
    CLASSIFY = "classify"  # Best: OpenAI
    EXTRACT = "extract"  # Best: Claude
    GENERATE_CODE = "generate_code"  # Best: Claude
    MULTIMODAL = "multimodal"  # Best: Gemini


# Optimal provider for each task type
TASK_PROVIDER_MAP: dict[AITaskType, list[AIProvider]] = {
    AITaskType.SEARCH: [AIProvider.PERPLEXITY, AIProvider.OPENAI],
    AITaskType.SUMMARIZE: [AIProvider.OPENAI, AIProvider.ANTHROPIC, AIProvider.GOOGLE],
    AITaskType.ANALYZE: [AIProvider.ANTHROPIC, AIProvider.OPENAI, AIProvider.GOOGLE],
    AITaskType.CLASSIFY: [AIProvider.OPENAI, AIProvider.ANTHROPIC, AIProvider.GOOGLE],
    AITaskType.EXTRACT: [AIProvider.ANTHROPIC, AIProvider.OPENAI, AIProvider.GOOGLE],
    AITaskType.GENERATE_CODE: [AIProvider.ANTHROPIC, AIProvider.OPENAI],
    AITaskType.MULTIMODAL: [AIProvider.GOOGLE, AIProvider.OPENAI],
}


@dataclass
class AIResponse:
    """Response from AI API."""

    content: str
    provider: AIProvider
    model: str
    usage: dict[str, int] | None = None
    raw_response: Any = None


class BaseAIClient(ABC):
    """Abstract base class for AI clients."""

    provider: AIProvider

    @abstractmethod
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        """Send completion request to AI API."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available (has valid API key)."""
        pass


class OpenAIClient(BaseAIClient):
    """OpenAI API client."""

    provider = AIProvider.OPENAI

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self._client: Any = None

    def is_available(self) -> bool:
        return self.api_key is not None

    async def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self.api_key.get_secret_value() if self.api_key else None
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        client = await self._get_client()
        model = kwargs.get("model", self.model)

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4096),
        )

        return AIResponse(
            content=response.choices[0].message.content or "",
            provider=self.provider,
            model=model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            raw_response=response,
        )


class AnthropicClient(BaseAIClient):
    """Anthropic Claude API client."""

    provider = AIProvider.ANTHROPIC

    def __init__(self) -> None:
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model
        self._client: Any = None

    def is_available(self) -> bool:
        return self.api_key is not None

    async def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(
                api_key=self.api_key.get_secret_value() if self.api_key else None
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        client = await self._get_client()
        model = kwargs.get("model", self.model)

        response = await client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get("max_tokens", 4096),
        )

        return AIResponse(
            content=response.content[0].text if response.content else "",
            provider=self.provider,
            model=model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
            raw_response=response,
        )


class GoogleClient(BaseAIClient):
    """Google Gemini API client."""

    provider = AIProvider.GOOGLE

    def __init__(self) -> None:
        self.api_key = settings.google_api_key
        self.model = settings.google_model
        self._client: Any = None

    def is_available(self) -> bool:
        return self.api_key is not None

    async def _get_client(self) -> Any:
        if self._client is None:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key.get_secret_value() if self.api_key else None)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        client = await self._get_client()

        # Run in executor since google-generativeai is not fully async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: client.generate_content(prompt))

        return AIResponse(
            content=response.text if response.text else "",
            provider=self.provider,
            model=self.model,
            raw_response=response,
        )


class PerplexityClient(BaseAIClient):
    """Perplexity API client (OpenAI-compatible)."""

    provider = AIProvider.PERPLEXITY

    def __init__(self) -> None:
        self.api_key = settings.perplexity_api_key
        self.model = settings.perplexity_model
        self._client: Any = None

    def is_available(self) -> bool:
        return self.api_key is not None

    async def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self.api_key.get_secret_value() if self.api_key else None,
                base_url="https://api.perplexity.ai",
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        client = await self._get_client()
        model = kwargs.get("model", self.model)

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

        return AIResponse(
            content=response.choices[0].message.content or "",
            provider=self.provider,
            model=model,
            raw_response=response,
        )


class AIOrchestrator:
    """
    AI API Orchestrator with fallback and task-based routing.

    Supports:
    - Automatic fallback when primary provider fails
    - Task-specific provider routing (e.g., search -> Perplexity)
    - Parallel requests to multiple providers
    """

    def __init__(self) -> None:
        self.clients: dict[AIProvider, BaseAIClient] = {
            AIProvider.OPENAI: OpenAIClient(),
            AIProvider.ANTHROPIC: AnthropicClient(),
            AIProvider.GOOGLE: GoogleClient(),
            AIProvider.PERPLEXITY: PerplexityClient(),
        }

    def get_available_providers(self) -> list[AIProvider]:
        """Get list of providers with valid API keys."""
        return [provider for provider, client in self.clients.items() if client.is_available()]

    def get_providers_for_task(self, task_type: AITaskType) -> list[AIProvider]:
        """Get ordered list of providers for a specific task type."""
        preferred = TASK_PROVIDER_MAP.get(task_type, list(AIProvider))
        available = self.get_available_providers()
        return [p for p in preferred if p in available]

    async def request(
        self,
        prompt: str,
        task_type: AITaskType = AITaskType.SUMMARIZE,
        preferred_provider: AIProvider | None = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> AIResponse:
        """
        Send request to AI with automatic fallback.

        Args:
            prompt: The prompt to send
            task_type: Type of task for optimal provider selection
            preferred_provider: Override automatic provider selection
            timeout: Request timeout in seconds
            **kwargs: Additional arguments passed to the AI client

        Returns:
            AIResponse with content and metadata

        Raises:
            RuntimeError: If all providers fail
        """
        if preferred_provider and self.clients[preferred_provider].is_available():
            providers = [preferred_provider]
        else:
            providers = self.get_providers_for_task(task_type)

        if not providers:
            raise RuntimeError("No AI providers available. Check your API keys.")

        last_error: Exception | None = None

        for provider in providers:
            client = self.clients[provider]
            try:
                logger.info("ai_request_start", provider=provider.value, task_type=task_type.value)

                response = await asyncio.wait_for(
                    client.complete(prompt, **kwargs),
                    timeout=timeout,
                )

                logger.info(
                    "ai_request_success",
                    provider=provider.value,
                    model=response.model,
                )
                return response

            except asyncio.TimeoutError:
                logger.warning("ai_request_timeout", provider=provider.value)
                last_error = TimeoutError(f"{provider.value} request timed out")

            except Exception as e:
                logger.warning("ai_request_failed", provider=provider.value, error=str(e))
                last_error = e

        raise RuntimeError(f"All AI providers failed. Last error: {last_error}")

    async def request_parallel(
        self,
        prompt: str,
        providers: list[AIProvider] | None = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> list[AIResponse]:
        """
        Send parallel requests to multiple providers.

        Useful for comparing responses or getting diverse perspectives.
        """
        if providers is None:
            providers = self.get_available_providers()

        tasks = []
        for provider in providers:
            client = self.clients[provider]
            if client.is_available():
                tasks.append(
                    asyncio.wait_for(
                        client.complete(prompt, **kwargs),
                        timeout=timeout,
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = []
        for result in results:
            if isinstance(result, AIResponse):
                responses.append(result)
            else:
                logger.warning("parallel_request_failed", error=str(result))

        return responses

    async def collaborate(
        self,
        initial_prompt: str,
        pipeline: list[tuple[AITaskType, str]],
        **kwargs: Any,
    ) -> list[AIResponse]:
        """
        Run a collaboration pipeline where output of one step feeds into the next.

        Args:
            initial_prompt: Starting prompt
            pipeline: List of (task_type, prompt_template) tuples
                      prompt_template can include {previous_response}

        Example:
            await orchestrator.collaborate(
                "Latest news about Physical AI",
                [
                    (AITaskType.SEARCH, "Search for: {previous_response}"),
                    (AITaskType.SUMMARIZE, "Summarize: {previous_response}"),
                    (AITaskType.ANALYZE, "Analyze trends: {previous_response}"),
                ]
            )
        """
        responses = []
        current_input = initial_prompt

        for task_type, prompt_template in pipeline:
            prompt = prompt_template.format(previous_response=current_input)
            response = await self.request(prompt, task_type=task_type, **kwargs)
            responses.append(response)
            current_input = response.content

        return responses


# Global orchestrator instance
ai_orchestrator = AIOrchestrator()
