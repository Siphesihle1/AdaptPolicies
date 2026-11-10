"""Optional local request measurements for reproducible experiment exports."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def record_completion(
    purpose: str,
    prompt: str,
    options: dict[str, Any],
    elapsed: float,
    response: Any = None,
    error: Exception | None = None,
) -> None:
    destination = os.getenv("LLM_METRICS_FILE")
    if not destination:
        return
    from . import telemetry

    choice = response.choices[0] if response is not None else None
    usage = getattr(response, "usage", None)
    row = {
        **telemetry.experiment_attributes(),
        "thread_id": telemetry._active_thread.get(),
        "purpose": purpose,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "request_parameters": options,
        "elapsed_seconds": elapsed,
        "finish_reason": getattr(choice, "finish_reason", None),
        "usage": usage.model_dump() if usage is not None else None,
        "output": choice.message.content if choice is not None else None,
        "error": f"{type(error).__name__}: {error}" if error else None,
    }
    with Path(destination).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")
