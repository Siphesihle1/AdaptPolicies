"""Configuration-driven provider selection and generation."""

from typing import Optional

from .config import get_llm_settings
from . import telemetry
from .providers import LLMProvider, LMOllama, LLMOpenAI, LLMAnthropic

PROVIDERS = {
    "ollama": LMOllama,
    "openai": LLMOpenAI,
    "lm_studio": LLMOpenAI,
    "anthropic": LLMAnthropic,
}


def get_provider() -> LLMProvider:
    settings = get_llm_settings()
    return PROVIDERS[settings["provider"]](settings)


@telemetry.op
def generate(
    prompt: str,
    purpose: str = "plan",
    *,
    __weave: Optional[dict[str, str]] = None,
) -> str:
    """Generate text; the telemetry decorator consumes optional __weave metadata."""
    provider = get_provider()
    settings = provider.settings
    if purpose not in {"plan", "assertion"}:
        raise ValueError("purpose must be plan or assertion")
    return provider.generate(prompt, settings[purpose], purpose)
