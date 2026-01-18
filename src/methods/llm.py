import os
from ollama import Client, GenerateResponse, Options
from urllib.parse import urlparse
import weave

from typing import List, Tuple, Optional


weave.init(os.getenv("PROJECT_NAME", ""))


def is_host(url: str, host: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname or parsed.path
    return hostname == host


@weave.op
def LM(
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
