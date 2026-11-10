"""LLM provider implementations and their request/response handling."""

from abc import ABC, abstractmethod
from typing import Any, Optional

import json
import os
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ollama import Client
from openai import OpenAI

from .config import get_llm_settings
from .generation_metrics import record_completion


def required_key(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Set {name} in the environment for this provider")
    return value


class LLMProvider(ABC):
    def __init__(self, settings: Optional[dict[str, Any]] = None):
        self.settings = settings if settings is not None else get_llm_settings()

    @abstractmethod
    def generate(self, prompt: str, options: dict[str, Any], purpose: str) -> str:
        """Generate text using this provider's request and response format."""
        raise NotImplementedError


class LMOllama(LLMProvider):
    def generate(self, prompt: str, options: dict[str, Any], purpose: str) -> str:
        settings = self.settings

        headers = None
        if urlparse(settings["base_url"]).hostname == "ollama.com":
            headers = {
                "Authorization": "Bearer " + required_key("OLLAMA_CLOUD_API_KEY")
            }
        # Preserve the existing chat-based assertion path and generate-based plans.
        if purpose == "assertion":

            key = required_key("OLLAMA_CLOUD_API_KEY") if headers else "ollama"
            with OpenAI(
                base_url=settings["base_url"].rstrip("/") + "/v1",
                api_key=key,
                timeout=settings["timeout"],
            ) as chat:
                response = chat.chat.completions.create(
                    model=settings["model"],
                    messages=[{"role": "user", "content": prompt}],
                    **options,
                )
            return response.choices[0].message.content or ""
        client = Client(
            host=settings["base_url"], headers=headers, timeout=settings["timeout"]
        )
        response = client.generate(model=settings["model"], prompt=prompt, **options)
        return response.response or ""


class LLMOpenAI(LLMProvider):
    def generate(self, prompt: str, options: dict[str, Any], purpose: str) -> str:

        # The SDK requires a nonempty value; local LM Studio needs no credential.
        key = (
            "lm-studio"
            if self.settings["provider"] == "lm_studio"
            else required_key("OPENAI_API_KEY")
        )
        with OpenAI(
            base_url=self.settings["base_url"],
            api_key=key,
            timeout=self.settings["timeout"],
            max_retries=0,
        ) as client:
            started = perf_counter()
            try:
                response = client.chat.completions.create(
                    model=self.settings["model"],
                    messages=[{"role": "user", "content": prompt}],
                    **options,
                )
            except Exception as error:
                record_completion(
                    purpose, prompt, options, perf_counter() - started, error=error
                )
                raise
            record_completion(
                purpose, prompt, options, perf_counter() - started, response=response
            )
        return response.choices[0].message.content or ""


class LLMAnthropic(LLMProvider):
    def generate(self, prompt: str, options: dict[str, Any], purpose: str) -> str:
        settings = self.settings
        payload = {
            "model": settings["model"],
            "messages": [{"role": "user", "content": prompt}],
            **options,
        }
        request = Request(
            settings["base_url"].rstrip("/") + "/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": required_key("ANTHROPIC_API_KEY"),
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings["timeout"]) as response:
                result = json.load(response)
        except HTTPError as error:
            raise RuntimeError(
                f"Anthropic request failed (HTTP {error.code})"
            ) from None
        except URLError:
            raise RuntimeError(
                "Could not connect to the configured Anthropic endpoint"
            ) from None
        return "".join(
            block["text"] for block in result["content"] if block["type"] == "text"
        )
