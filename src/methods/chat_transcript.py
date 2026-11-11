"""A recorded chat presentation of planning and simulator execution."""

import base64
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from io import BytesIO
from html import escape
import json
import re
from typing import Any, Iterator

from PIL import Image


@dataclass
class PlanChatTranscript:
    messages: list[dict[str, Any]] = field(default_factory=list)


_active: ContextVar[PlanChatTranscript | None] = ContextVar(
    "plan_chat_transcript", default=None
)


@contextmanager
def capture_transcript(transcript: PlanChatTranscript) -> Iterator[None]:
    token = _active.set(transcript)
    try:
        yield
    finally:
        _active.reset(token)


def append_message(role: str, content: str | list[dict[str, Any]]) -> None:
    transcript = _active.get()
    if transcript is not None:
        transcript.messages.append({"role": role, "content": content})


def record_request(prompt: str, purpose: str) -> None:
    # Weave treats any literal <...> as HTML and disables Markdown for the
    # entire message, including fenced blocks. This affects display only.
    append_message(
        "user", f"**{purpose.capitalize()} prompt**\n\n{format_prompt(prompt)}"
    )


def format_prompt(prompt: str) -> str:
    """Escape markup-like prompt tags without displaying entities as code.

    Weave's HTML heuristic also examines fenced excerpts. Excerpts containing
    tags use quoted lines with preserved spacing so those tags render literally.
    Other fenced code is preserved verbatim.
    """
    parts = []
    offset = 0
    for match in re.finditer(
        r"^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$", prompt, re.MULTILINE | re.DOTALL
    ):
        parts.append(format_prompt_prose(prompt[offset : match.start()]))
        block = match.group()
        if re.search(r"<[^>]+>", block):
            body = block.split("\n", 1)[1].rsplit("\n", 1)[0]
            parts.append(
                "\n".join(
                    "> " + escape(line, quote=False).replace(" ", "&nbsp;") + "  "
                    for line in body.splitlines()
                )
            )
        else:
            parts.append(block)
        offset = match.end()
    parts.append(format_prompt_prose(prompt[offset:]))
    return "".join(parts)


def format_prompt_prose(text: str) -> str:
    """Keep an unfenced function header and its indented example together."""
    parts = []
    offset = 0
    for match in re.finditer(
        r"^def [^\n]+:[ \t]*(?:\n(?:[ \t]+[^\n]*(?:\n|$)|\n(?=[ \t]))*)?",
        text,
        re.MULTILINE,
    ):
        parts.append(escape(text[offset : match.start()], quote=False))
        snippet = match.group().rstrip("\n")
        if re.search(r"<[^>]+>", snippet):
            parts.append(
                "\n".join(
                    "> " + escape(line, quote=False).replace(" ", "&nbsp;") + "  "
                    for line in snippet.splitlines()
                )
            )
        else:
            parts.append(code_block(snippet, "python"))
        parts.append("\n\n")
        offset = match.end()
    parts.append(escape(text[offset:], quote=False))
    return "".join(parts)


def code_block(content: str, language: str) -> str:
    """Preserve snippet indentation and avoid closing on embedded fences."""
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}{language}\n{content}\n{fence}"


def record_response(response: str, purpose: str) -> None:
    label = {"plan": "Generated plan", "assertion": "Assertion answer",
             "cap_policy": "CaP policy", "cap_function": "CaP helper",
             "cap_objects": "CaP object program", "cap_question": "CaP question program"}[purpose]
    append_message("assistant", f"**{label}**\n\n{code_block(response, 'python')}")


def record_span_start(name: str, inputs: dict[str, Any]) -> None:
    if _active.get() is None:
        return
    if name == "plan_action":
        arguments = ", ".join(repr(obj) for obj in inputs["objects"])
        snippet = f"{inputs['action']}({arguments})"
        append_message("assistant", f"**Action**\n\n{code_block(snippet, 'python')}")
    elif name == "simulator_action":
        append_message(
            "assistant",
            f"**Simulator request**\n\n{escape(inputs['script_instruction'], quote=False)}",
        )


def record_span_end(
    name: str,
    inputs: dict[str, Any],
    output: dict[str, Any],
    error: BaseException | None = None,
) -> None:
    if _active.get() is None:
        return
    if error is not None:
        detail = f"{type(error).__name__}: {error}"
        append_message("user", f"**{name} error**\n\n{escape(detail, quote=False)}")
    elif name in {"plan_action", "simulator_action", "observe_state"}:
        label = {
            "plan_action": "Action result",
            "simulator_action": "Simulator result",
            "observe_state": "State observation",
        }[name]
        # JSON's Unicode escapes preserve the decoded native values while
        # avoiding Weave's HTML-detection heuristic inside the code fence.
        payload = json.dumps({**inputs, **output}, indent=2, default=str)
        payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
        append_message(
            "user",
            f"**{label}**\n\n" + code_block(payload, "json"),
        )
    elif name in {"initial_image", "get_observation"}:
        image = output.get("image")
        if isinstance(image, Image.Image):
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            append_message(
                "user",
                [
                    {
                        "type": "text",
                        "text": (
                            "Initial image observation"
                            if name == "initial_image"
                            else "Image observation"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded}"},
                    },
                ],
            )
