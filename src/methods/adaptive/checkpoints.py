"""What failed and where: failure records, generated-code frames and control signals.

Generated programs are compiled with filenames beginning ``<ap-`` so the trusted
checkpoint, action and helper wrappers can find the generated call stack and
the caller's variables without the generated code's cooperation.
"""

from dataclasses import dataclass, field
from typing import Any

from virtual_home.virtualhome_types import ObjectRef

GENERATED = "<ap-"


def policy_filename(version):
    return f"<ap-policy:{version}>"


def helper_filename(name, version):
    return f"<ap-helper:{name}:{version}>"


def recover_filename(number):
    return f"<ap-recover:{number}>"


# Control signals derive from BaseException so generated `except Exception`
# clauses cannot swallow them; the AP validator also rejects bare `except:`.
class Replan(BaseException):
    """Abandon the running policy and continue with a newly generated one."""

    def __init__(self, failure):
        super().__init__("replan")
        self.failure = failure


class RegenerateHelper(BaseException):
    """The named helper was regenerated; its wrapper calls it again."""

    def __init__(self, name):
        super().__init__(name)
        self.name = name


class NoProgress(BaseException):
    """The same failure recurred after a replan without any successful action."""

    def __init__(self, failure):
        super().__init__("stuck_no_progress")
        self.failure = failure


@dataclass(frozen=True)
class Frame:
    kind: str  # policy, helper or recover
    function: str
    filename: str
    lineno: int
    helper: str | None = None


@dataclass
class Failure:
    trigger: str  # checkpoint, action or exception
    frames: list[Frame]
    bindings: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    check_source: str | None = None
    action: str | None = None
    arguments: tuple = ()
    message: str | None = None
    exception: str | None = None

    @property
    def site(self):
        """Where it failed: the innermost generated line, or the trigger alone."""
        frame = self.frames[0] if self.frames else None
        return (self.trigger, frame.filename if frame else None, frame.lineno if frame else None)

    def signature(self):
        """What failed, independent of the program version that failed."""
        return (self.trigger, self.description, self.action,
                tuple(describe(argument) for argument in self.arguments),
                self.message, self.exception)

    def summary(self):
        if self.trigger == "checkpoint":
            return f"checkpoint failed: {self.description} (check: {self.check_source})"
        if self.trigger == "action":
            call = f"{self.action}({', '.join(describe(a) for a in self.arguments)})"
            return f"{call} failed: {self.message}"
        return f"{self.exception}"

    def record(self):
        return {"trigger": self.trigger, "summary": self.summary(), "description": self.description,
                "check_source": self.check_source, "action": self.action,
                "arguments": [describe(a) for a in self.arguments], "message": self.message,
                "exception": self.exception,
                "frames": [{"kind": f.kind, "function": f.function, "line": f.lineno, "helper": f.helper}
                           for f in self.frames],
                "bindings": {name: describe(value) for name, value in self.bindings.items()}}


def frame_of(code_filename, function, lineno):
    if code_filename.startswith("<ap-policy:"):
        return Frame("policy", function, code_filename, lineno)
    if code_filename.startswith("<ap-helper:"):
        return Frame("helper", function, code_filename, lineno, code_filename.split(":")[1])
    return Frame("recover", function, code_filename, lineno)


def generated_frames(frame):
    """Generated frames from `frame` outwards, innermost first."""
    frames = []
    while frame is not None:
        code = frame.f_code
        if code.co_filename.startswith(GENERATED):
            frames.append(frame_of(code.co_filename, code.co_name, frame.f_lineno))
        frame = frame.f_back
    return frames


def caller_frame(frame):
    """The innermost generated frame at or outside `frame`."""
    while frame is not None and not frame.f_code.co_filename.startswith(GENERATED):
        frame = frame.f_back
    return frame


def traceback_frames(traceback):
    """Generated frames on an exception's path, innermost first, and the innermost frame object."""
    frames, innermost = [], None
    while traceback is not None:
        code = traceback.tb_frame.f_code
        if code.co_filename.startswith(GENERATED):
            frames.append(frame_of(code.co_filename, code.co_name, traceback.tb_lineno))
            innermost = traceback.tb_frame
        traceback = traceback.tb_next
    return list(reversed(frames)), innermost


def bindings_of(frame):
    """Caller variables the recovery may use: object references and plain values."""
    if frame is None:
        return {}
    return {name: value for name, value in frame.f_locals.items()
            if not name.startswith("_") and bindable(value)}


def bindable(value, depth=0):
    if isinstance(value, (ObjectRef, str, int, float, bool)) or value is None:
        return True
    if depth < 2 and isinstance(value, (list, tuple, set, frozenset)):
        return all(bindable(item, depth + 1) for item in value)
    if depth < 2 and isinstance(value, dict):
        return all(bindable(k, depth + 1) and bindable(v, depth + 1) for k, v in value.items())
    return False


def describe(value):
    """Model-facing text for a value: object references appear by class name."""
    if isinstance(value, ObjectRef):
        return value.name
    if isinstance(value, (list, tuple, set, frozenset)):
        items = ", ".join(describe(item) for item in value)
        return f"[{items}]" if isinstance(value, list) else f"({items})"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{describe(k)}: {describe(v)}" for k, v in value.items()) + "}"
    return repr(value)


TERMINAL_MESSAGES = ("_limit", "uncertain_native_state", "deadline")


def is_terminal(error):
    """Errors that end the episode instead of starting a recovery (D2)."""
    if isinstance(error, TimeoutError):
        return True
    text = str(error)
    return isinstance(error, RuntimeError) and any(marker in text for marker in TERMINAL_MESSAGES)


def exception_text(error):
    return f"{type(error).__name__}: {error}"
