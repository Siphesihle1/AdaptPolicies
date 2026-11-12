"""Process-wide configuration with native request parameters per provider/model."""

from functools import lru_cache
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = {"ollama", "openai", "lm_studio", "anthropic"}
CAP_PURPOSES = {"cap_policy", "cap_function", "cap_objects", "cap_question"}


@lru_cache(maxsize=1)
def get_config() -> dict[str, Any]:
    selection = os.getenv("ADAPT_CONFIG", "dev")
    path = (
        ROOT / "config" / f"{selection}.yml"
        if selection in {"dev", "live"}
        else Path(selection)
    )
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict) or not {"llm", "weave"} <= set(config) or set(config) - {"llm", "weave", "cap"}:
        raise ValueError("Configuration requires llm and weave; optional cap section")
    if "cap" in config:
        from .shared.lmp_runtime import Limits
        if not isinstance(config["cap"], dict):
            raise ValueError("cap must be a runtime limits mapping")
        try:
            Limits(**config["cap"])
        except TypeError as error:
            raise ValueError(f"Invalid cap runtime settings: {error}") from error
    llm = config["llm"]
    if not isinstance(llm, dict) or set(llm) != {"provider", "model", "providers"}:
        raise ValueError("llm requires provider, model and providers settings")
    if llm["provider"] not in PROVIDERS:
        raise ValueError(f"llm.provider must be one of {sorted(PROVIDERS)}")
    if not isinstance(llm["model"], str) or not llm["model"].strip():
        raise ValueError("llm.model must be a nonempty string")
    providers = llm["providers"]
    if not isinstance(providers, dict) or set(providers) - PROVIDERS:
        raise ValueError("llm.providers must contain supported provider names")
    for provider, settings in providers.items():
        if not isinstance(settings, dict) or set(settings) != {
            "base_url",
            "timeout",
            "models",
        }:
            raise ValueError(f"{provider} requires base_url, timeout and models")
        if not isinstance(settings["base_url"], str):
            raise ValueError("base_url must be an HTTP(S) URL")
        endpoint = urlparse(settings["base_url"])
        if (
            endpoint.scheme not in {"http", "https"}
            or not endpoint.hostname
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError(
                "base_url must be an HTTP(S) URL without credentials, query, or fragment"
            )
        timeout = settings["timeout"]
        if type(timeout) not in {int, float} or timeout <= 0:
            raise ValueError("timeout must be positive")
        models = settings["models"]
        if not isinstance(models, dict) or not models:
            raise ValueError(f"{provider}.models must contain model settings")
        for model, model_settings in models.items():
            if not isinstance(model, str) or not model.strip():
                raise ValueError("Model names must be nonempty strings")
            if (not isinstance(model_settings, dict)
                or not ({"plan", "assertion"} <= set(model_settings) or CAP_PURPOSES <= set(model_settings))
                or set(model_settings) - ({"plan", "assertion"} | CAP_PURPOSES)):
                raise ValueError(
                    f"{provider}/{model} requires plan and assertion settings"
                )
            for purpose, request in model_settings.items():
                validate_request_parameters(request, f"{provider}/{model}/{purpose}")
    if (
        llm["provider"] not in providers
        or llm["model"] not in providers[llm["provider"]]["models"]
    ):
        raise ValueError("Selected provider/model has no configured settings")
    logging = config["weave"]
    if (
        not isinstance(logging, dict)
        or set(logging) != {"enabled"}
        or type(logging["enabled"]) is not bool
    ):
        raise ValueError("weave.enabled must be a YAML boolean")
    return config


def validate_request_parameters(parameters: Any, location: str) -> None:
    """Check structure and keep credentials out of exported configuration.

    Parameter names and values otherwise belong to the selected native API.
    """
    if not isinstance(parameters, dict) or any(
        not isinstance(key, str) for key in parameters
    ):
        raise ValueError(f"{location} must be a mapping of native request parameters")
    for key in parameters:
        if key.lower() in {
            "api_key",
            "authorization",
            "headers",
            "extra_headers",
            "model",
            "messages",
            "prompt",
        }:
            raise ValueError(f"{location}: {key} belongs outside generation settings")


def get_llm_settings() -> dict[str, Any]:
    """Select connection settings and native profiles without translating parameters."""
    llm = get_config()["llm"]
    provider = llm["providers"][llm["provider"]]
    return {
        "provider": llm["provider"],
        "model": llm["model"],
        "base_url": provider["base_url"],
        "timeout": provider["timeout"],
        **provider["models"][llm["model"]],
    }


def require_method_profiles(method: str) -> None:
    required = CAP_PURPOSES if method == "cap" else {"plan", "assertion"}
    missing = required - get_llm_settings().keys()
    if missing:
        raise ValueError(f"{method} requires explicit model profiles: {sorted(missing)}")


if __name__ == "__main__":
    print(get_config()["llm"]["provider"])
