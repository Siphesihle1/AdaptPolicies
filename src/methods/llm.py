import os
from ollama import Client, GenerateResponse, Options
from openai import OpenAI
from urllib.parse import urlparse
from openai.types.completion import Completion
import weave

from typing import List, Tuple, Optional

wandb_project_name = os.getenv("PROJECT_NAME", "")
entity, project = wandb_project_name.split("/", 1)
weave.init(os.getenv("PROJECT_NAME", ""))


def is_host(url: str, host: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname or parsed.path
    return hostname == host


@weave.op
def LMOllama(
    prompt: str,
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    stop: Optional[str | List[str]] = None,
    logprobs=True,
    frequency_penalty: Optional[float] = None,
    think=True,
) -> Tuple[GenerateResponse, str]:
    headers = (
        {"Authorization": "Bearer " + os.environ.get("OLLAMA_CLOUD_API_KEY", "")}
        if is_host(os.getenv("OLLAMA_HOST", ""), "ollama.com")
        else None
    )
    client = Client(
        host=os.getenv("OLLAMA_HOST"),
        headers=headers,
    )
    options: Options = Options(
        temperature=temperature,
        num_predict=max_tokens,
        frequency_penalty=frequency_penalty,
        stop=stop,
    )

    response = client.generate(
        model=model, prompt=prompt, logprobs=logprobs, options=options, think=think
    )

    return response, response.response.strip()


@weave.op
def LLMOpenAI(
    prompt: str,
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    stop: Optional[str | List[str]] = None,
    frequency_penalty: Optional[float] = None,
) -> Tuple[Completion, str]:
    ollama_host = os.getenv("OLLAMA_HOST", "")
    api_key = (
        os.getenv("OLLAMA_CLOUD_API_KEY", "")
        if is_host(ollama_host, "ollama.com")
        else "ollama"
    )

    client = OpenAI(base_url=f"{ollama_host}/v1", api_key=api_key)

    response = client.completions.create(
        model=model,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        stop=stop,
        frequency_penalty=frequency_penalty,
    )

    return response, response.choices[0].text.strip()
