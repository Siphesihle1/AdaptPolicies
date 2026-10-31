"""Process-wide configuration"""

from functools import lru_cache
import os
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = {"ollama", "openai", "lm_studio", "anthropic"}
COMMON_OPTIONS = {"temperature", "max_tokens", "stop"}
PROVIDER_OPTIONS = {
    "ollama": {"think", "frequency_penalty"},
    "openai": {"frequency_penalty", "reasoning_effort"},
    "lm_studio": {"frequency_penalty", "reasoning_effort"},
    "anthropic": set(),
}


@lru_cache(maxsize=1)
def get_config():
    selection = os.getenv("ADAPT_CONFIG", "dev")
    path = (
        ROOT / "config" / f"{selection}.yml"
        if selection in {"dev", "live"}
        else Path(selection)
    )
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict) or set(config) != {"llm", "weave"}:
        raise ValueError("Configuration must contain only llm and weave sections")
    llm = config["llm"]
    if not isinstance(llm, dict) or set(llm) - {
        "provider",
        "model",
        "base_url",
        "timeout",
        "generation",
    }:
        raise ValueError(
            "Invalid llm settings; credentials belong in environment variables"
        )
    if llm.get("provider") not in PROVIDERS:
        raise ValueError(f"llm.provider must be one of {sorted(PROVIDERS)}")
    if not isinstance(llm.get("model"), str) or not llm["model"].strip():
        raise ValueError("llm.model must be a nonempty string")
    endpoint = urlparse(llm.get("base_url", ""))
    if (
        endpoint.scheme not in {"http", "https"}
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError(
            "llm.base_url must be an HTTP(S) URL without credentials, query, or fragment"
        )
    timeout = llm.get("timeout", 120)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ValueError("llm.timeout must be positive")
    llm["timeout"] = timeout
    generation = llm.get("generation")
    if not isinstance(generation, dict) or set(generation) != {"plan", "assertion"}:
        raise ValueError("llm.generation requires plan and assertion settings")
    for purpose, settings in generation.items():
        if not isinstance(settings, dict) or set(settings) - COMMON_OPTIONS - PROVIDERS:
            raise ValueError(f"Unsupported generation settings for {purpose}")
        for provider in PROVIDERS & settings.keys():
            options = settings[provider]
            if (
                not isinstance(options, dict)
                or set(options) - PROVIDER_OPTIONS[provider]
            ):
                raise ValueError(f"Unsupported {provider} options for {purpose}")
        tokens = settings.get("max_tokens")
        if tokens is not None and (type(tokens) is not int or tokens <= 0):
            raise ValueError("max_tokens must be a positive integer")
        temperature = settings.get("temperature")
        if temperature is not None and (
            type(temperature) not in {int, float} or temperature < 0
        ):
            raise ValueError("temperature must be a nonnegative number")
        stop = settings.get("stop")
        if stop is not None and not (
            isinstance(stop, str)
            or isinstance(stop, list)
            and all(isinstance(item, str) for item in stop)
        ):
            raise ValueError("stop must be a string or list of strings")
    logging = config["weave"]
    if (
        not isinstance(logging, dict)
        or set(logging) != {"enabled"}
        or type(logging["enabled"]) is not bool
    ):
        raise ValueError("weave.enabled must be a YAML boolean")
    return config


if __name__ == "__main__":
    print(get_config()["llm"]["provider"])
