"""Failure-context prompt sections: program, failure, progress and bindings.

Lengths are bounded so a long episode cannot crowd out the rest of the prompt.
"""

from .checkpoints import describe

MAX_PROGRESS_ENTRIES = 40
MAX_RECOVERY_ENTRIES = 8


def program_section(sources, failure):
    """Running sources with the failing line marked and calling lines noted.

    `sources` maps a generated filename to (label, source) for the current
    policy and helper versions.
    """
    marks = {}
    for index, frame in enumerate(failure.frames):
        marks.setdefault((frame.filename, frame.lineno),
                         "# <- failed here" if index == 0 else "# <- called from here")
    blocks = []
    for filename, (label, source) in sources.items():
        lines = source.splitlines()
        for number, line in enumerate(lines, start=1):
            mark = marks.get((filename, number))
            if mark:
                lines[number - 1] = f"{line}  {mark}"
        blocks.append(f"# {label}\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def failure_section(failure):
    kind = {"checkpoint": "checkpoint", "action": "action", "exception": "exception"}[failure.trigger]
    lines = [f"Kind: {kind}"]
    if failure.trigger == "checkpoint":
        lines += [f"Expected state: {failure.description}", f"Check: {failure.check_source}"]
    elif failure.trigger == "action":
        call = f"{failure.action}({', '.join(describe(a) for a in failure.arguments)})"
        lines += [f"Action: {call}", f"Message: {failure.message}"]
    else:
        lines += [f"Exception: {failure.exception}"]
    if failure.frames:
        frame = failure.frames[0]
        where = f"helper {frame.helper}" if frame.kind == "helper" else frame.kind
        lines.append(f"Location: {where}, line {frame.lineno}")
    return "\n".join(lines)


def progress_section(trace, recoveries):
    entries = []
    for event in trace[-MAX_PROGRESS_ENTRIES:]:
        if event["kind"] == "action":
            text = f"{event['call']} {event['status']}"
            if event.get("recovered"):
                text += " (recovered)"
            if event["status"] == "failed" and event.get("message"):
                text += f": {event['message']}"
            entries.append(text)
        elif event["kind"] == "checkpoint":
            entries.append(f"checkpoint passed: {event['description']}")
    omitted = len(trace) - MAX_PROGRESS_ENTRIES
    text = ("Completed so far:\n" + ("(earlier steps omitted)\n" if omitted > 0 else "")
            + ("\n".join(f"- {entry}" for entry in entries) if entries else "- nothing yet"))
    if recoveries:
        recent = recoveries[-MAX_RECOVERY_ENTRIES:]
        text += "\nEarlier recoveries in this episode:\n" + "\n".join(
            f"- {r['scope']} for '{r['failure']}': {'succeeded' if r['succeeded'] else 'failed'}"
            + (f" ({r['error']})" if r.get("error") else "") for r in recent)
    return text


def bindings_section(bindings):
    if not bindings:
        return "(none)"
    return "\n".join(f"{name} = {describe(value)}" for name, value in sorted(bindings.items()))
