from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import wraps
from importlib import import_module
import os
from typing import Any, Iterator

from .config import get_config, get_llm_settings
from .chat_transcript import (
    record_request,
    record_response,
    record_span_start,
    record_span_end,
)

_client = None
_active_thread: ContextVar[str | None] = ContextVar("weave_plan_thread", default=None)


def experiment_attributes() -> dict[str, Any]:
    """Metadata shared by every call in a named experiment run."""
    name = os.getenv("EXPERIMENT_NAME")
    if not name:
        return {}
    settings = get_llm_settings()
    values = {
        "experiment_name": name,
        "provider": settings["provider"],
        "model": settings["model"],
        "plan_temperature": settings["plan"].get("temperature"),
        "plan_max_tokens": settings["plan"].get("max_tokens"),
        "plan_reasoning_effort": settings["plan"].get("reasoning_effort"),
    }
    if os.getenv("EXPERIMENT_RUN_ID"):
        values["run_id"] = os.environ["EXPERIMENT_RUN_ID"]
    if os.getenv("EXPERIMENT_REPEAT"):
        values["repeat_index"] = int(os.environ["EXPERIMENT_REPEAT"])
    return values


def reuse_cached_wandb_login():
    if os.getenv("WANDB_API_KEY"):
        return
    try:
        setup = import_module("wandb.sdk.wandb_setup")
        settings = setup.singleton().settings
        credential = settings.api_key
        if not credential:
            auth = import_module("wandb.sdk.lib.wbauth")
            credential = auth.read_netrc_auth(host=settings.base_url)
    except ImportError:
        # Older W&B versions use the credential lookup bundled with Weave.
        return
    if credential:
        os.environ["WANDB_API_KEY"] = credential


def align_weave_auth_transport():
    try:
        api = import_module("weave.compat.wandb.wandb_thin.internal_api")
        transport = import_module("gql.transport.httpx")
    except ImportError:
        return
    if getattr(api, "httpx", None) is not None and getattr(transport, "httpx", None):
        # gql may use httpx2 while Weave's bundled client imports httpx.
        # Match BasicAuth to that transport without changing either global library.
        api.httpx = transport.httpx  # type: ignore


def backend():
    global _client
    if not get_config()["weave"]["enabled"]:
        return None
    if _client is None:
        project = os.getenv("PROJECT_NAME")
        if not project:
            raise ValueError("PROJECT_NAME is required when Weave logging is enabled")
        weave = import_module("weave")

        reuse_cached_wandb_login()
        align_weave_auth_transport()
        weave.init(project)
        _client = weave
    return _client


def op(function):
    traced = None

    @wraps(function)
    def wrapped(*args, **kwargs):
        nonlocal traced
        is_generation = (
            function.__module__ == "methods.llm" and function.__name__ == "generate"
        )
        if is_generation:
            record_request(
                kwargs.get("prompt", args[0] if args else ""),
                kwargs.get("purpose", args[1] if len(args) > 1 else "plan"),
            )
        client = backend()
        if client is None:
            kwargs.pop("__weave", None)
            result = function(*args, **kwargs)
        else:
            if traced is None:
                traced = client.op(function)
            result = traced(*args, **kwargs)
        if is_generation:
            record_response(
                result, kwargs.get("purpose", args[1] if len(args) > 1 else "plan")
            )
        if function.__name__ == "get_observation":
            record_span_end("get_observation", {}, {"image": result})
        return result

    return wrapped


@contextmanager
def thread(**kwargs) -> Iterator[None]:
    """Reuse an active plan thread without resetting the SDK's turn lineage."""
    client = backend()
    identifier = kwargs.get("thread_id")
    if client is None or identifier is not None and _active_thread.get() == identifier:
        yield
        return
    token = _active_thread.set(identifier)
    try:
        with client.thread(**kwargs):
            yield
    finally:
        _active_thread.reset(token)


@contextmanager
def span(name: str, inputs: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Trace a step without serializing the simulator or agent instance.

    Callers fill the yielded output; nested LLM and observation calls inherit
    this step as their parent. Exceptions are recorded and still propagate.
    """
    output: dict[str, Any] = {}
    record_span_start(name, inputs)
    backend_module = backend()
    client = backend_module.get_client() if backend_module else None
    call = (
        client.create_call(name, inputs=inputs, display_name=name) if client else None
    )
    try:
        yield output
    except BaseException as error:
        record_span_end(name, inputs, output, error)
        if client:
            client.finish_call(call, output=output, exception=error)
        raise
    else:
        record_span_end(name, inputs, output)
        if client:
            client.finish_call(call, output=output)


def publish_plan_chat(
    messages: list[dict[str, Any]], final_message: str, task: str
) -> str | None:
    """Publish a chat-shaped transcript, without making or billing a model call."""
    backend_module = backend()
    if backend_module is None:
        return None
    client = backend_module.get_client()
    call = client.create_call(
        "plan_chat_transcript",
        inputs={"messages": messages},
        display_name=task,
        attributes={**experiment_attributes(), "source": "recorded_plan_execution"},
    )
    client.finish_call(
        call,
        output={
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": final_message},
                    "finish_reason": "stop",
                }
            ]
        },
    )
    return call.id


def attributes(values):
    client = backend()
    return client.attributes(values) if client else nullcontext()


def evaluation_logger(**kwargs):
    client = backend()
    return client.EvaluationLogger(**kwargs) if client else None
