"""Configuration-driven provider selection and generation."""

from typing import Optional

from .config import COMMON_OPTIONS, get_config
from . import telemetry
from .providers import LLMProvider, LMOllama, LLMOpenAI, LLMAnthropic

PROVIDERS = {
    "ollama": LMOllama,
    "openai": LLMOpenAI,
    "lm_studio": LLMOpenAI,
    "anthropic": LLMAnthropic,
}


def get_provider() -> LLMProvider:
    settings = get_config()["llm"]
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
    profile = settings["generation"][purpose]
    options = {
        key: value
        for key, value in profile.items()
        if key in COMMON_OPTIONS and value is not None
    }
    options.update(profile.get(settings["provider"], {}))
    return provider.generate(prompt, options, purpose)
