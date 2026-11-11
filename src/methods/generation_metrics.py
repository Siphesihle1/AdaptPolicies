"""Optional local request measurements for reproducible experiment exports."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from contextlib import contextmanager
from contextvars import ContextVar

_sink = ContextVar("generation_metrics_sink", default=None)


@contextmanager
def capture_completions(sink):
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)


def record_completion(
    purpose: str,
    prompt: str,
    options: dict[str, Any],
    elapsed: float,
    response: Any = None,
    error: Exception | None = None,
) -> None:
    destination = os.getenv("LLM_METRICS_FILE")
    if not destination and _sink.get() is None:
        return
    from . import telemetry

    choices = getattr(response, "choices", None)
    choice = choices[0] if choices else None
    usage = getattr(response, "usage", None)
    row = {
        **telemetry.experiment_attributes(),
        "thread_id": telemetry._active_thread.get(),
        "purpose": purpose,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "request_parameters": options,
        "elapsed_seconds": elapsed,
        "finish_reason": getattr(choice, "finish_reason", None),
        "usage": (usage.model_dump() if hasattr(usage, "model_dump") else usage),
        "output": choice.message.content if choice is not None else None,
        "error": f"{type(error).__name__}: {error}" if error else None,
    }
    if _sink.get() is not None:
        _sink.get()(row)
    if destination:
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
