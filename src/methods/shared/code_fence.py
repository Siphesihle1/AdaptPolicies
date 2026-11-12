"""Unwrap a response that is one Markdown code block (ProgPrompt and CaP)."""


def strip_code_fence(plan: str) -> tuple[str, bool]:
    """Remove one Markdown code block wrapping the whole response.

    Returns the plan and whether a wrapper was removed. Only a response that is a
    single ```...``` block is unwrapped; anything else is returned unchanged, so
    the format checks still reject stray or multiple fences.
    """
    lines = plan.strip().splitlines()
    if (
        len(lines) >= 2
        and lines[0].strip().startswith("```")
        and lines[-1].strip() == "```"
        and not any(line.strip().startswith("```") for line in lines[1:-1])
    ):
        return "\n".join(lines[1:-1]), True
    return plan, False
