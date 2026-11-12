"""Validated Python in a disposable spawned process with parent-owned environment RPC.

This is a capability-restricted interpreter process, not an OS security sandbox for
hostile Python. No simulator, evaluator, provider credentials, or raw graph is bound
in generated namespaces. Deadlines are enforced outside generated Python.

Shared by the language-model-program methods (Code as Policies and Adaptive
Policies). Each method supplies its session class and its trace labels.
"""

import ast
import builtins
from dataclasses import asdict, dataclass, fields, is_dataclass
from functools import partial
import multiprocessing as mp
from queue import Queue, Empty
from threading import Thread
from contextvars import copy_context
import time
import traceback


BUILTINS = {name: getattr(builtins, name) for name in (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "frozenset", "int",
    "len", "list", "max", "min", "range", "reversed", "round", "set", "sorted",
    "str", "sum", "tuple", "zip", "isinstance", "ValueError", "TypeError")}
ATTRIBUTES = {"episode_id", "id", "name", "status", "error", "observation_revision",
              "append", "extend", "pop", "remove", "index", "count", "sort", "reverse",
              "get", "items", "keys", "values", "add", "discard", "intersection",
              "union", "difference", "issubset", "lower", "upper", "strip", "split",
              "join", "startswith", "endswith", "replace"}
DENIED_NAMES = {"exec", "eval", "compile", "getattr", "setattr", "delattr", "globals",
                "locals", "vars", "dir", "type", "object", "super", "input", "print",
                "help", "breakpoint", "memoryview", "classmethod", "staticmethod"}


@dataclass(frozen=True)
class Limits:
    task_seconds: float = 120
    max_helpers: int = 24
    max_depth: int = 8
    max_model_requests: int = 32
    max_actions: int = 100
    max_queries: int = 1000
    max_source_bytes: int = 65536
    max_output_bytes: int = 1048576

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{field.name} must be positive")
            if field.name != "task_seconds" and type(value) is not int:
                raise ValueError(f"{field.name} must be an integer")
        if not time_is_finite(self.task_seconds):
            raise ValueError("task_seconds must be finite")


def time_is_finite(value):
    import math
    return math.isfinite(value)


def serialize(value):
    if is_dataclass(value):
        return {k: serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [serialize(v) for v in value]
    if value is None:
        return value
    # Subclasses become their plain base type: with Weave enabled, traced calls
    # return boxed values such as weave's BoxedStr. bool precedes int (its base).
    for base in (bool, int, float, str):
        if isinstance(value, base):
            return base(value)
    raise TypeError(f"Unsupported result type: {type(value).__name__}")


def validate(source, reserved=(), limit=65536):
    if not isinstance(source, str) or len(source.encode()) > limit:
        raise ValueError("source_size_limit")
    tree = ast.parse(source)
    denied = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal,
              ast.With, ast.AsyncWith, ast.AsyncFunctionDef, ast.Await, ast.Yield,
              ast.YieldFrom, ast.Delete)
    for node in ast.walk(tree):
        if isinstance(node, denied):
            raise ValueError(f"Forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Name):
            if node.id.startswith('_') or node.id in DENIED_NAMES:
                raise ValueError("Private names are forbidden")
            if isinstance(node.ctx, ast.Store) and node.id in reserved:
                raise ValueError(f"Reserved name: {node.id}")
        if isinstance(node, (ast.FunctionDef, ast.arg)):
            name = node.name if isinstance(node, ast.FunctionDef) else node.arg
            if name.startswith('_') or name in reserved:
                raise ValueError(f"Reserved name: {name}")
            if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.returns or
                    any(arg.annotation for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs)):
                raise ValueError("Decorators and annotations are forbidden")
            if isinstance(node, ast.arg) and node.annotation is not None:
                raise ValueError("Annotations are forbidden")
        if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar, ast.MatchMapping)):
            name = getattr(node, "name", None) or getattr(node, "rest", None)
            if name and (name in reserved or name.startswith('_') or name in DENIED_NAMES):
                raise ValueError(f"Reserved name: {name}")
        if isinstance(node, ast.Attribute):
            if not isinstance(node.ctx, ast.Load) or node.attr not in ATTRIBUTES:
                raise ValueError(f"Forbidden attribute: {node.attr}")
    return tree


class Budget:
    def __init__(self, limits):
        self.limits = limits
        self.deadline = time.monotonic() + limits.task_seconds
        self.counts = {"model_requests": 0, "actions": 0, "queries": 0}

    def consume(self, kind):
        self.check()
        self.counts[kind] += 1
        if self.counts[kind] > getattr(self.limits, "max_" + kind):
            raise RuntimeError(kind + "_limit")

    def check(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("task_deadline")


def _rpc(connection, name, args, kwargs, call_id=None):
    connection.send(("rpc", name, args, kwargs, call_id))
    status, value = connection.recv()
    if status != "ok":
        raise RuntimeError(value)
    return value


def _worker(connection, task, episode_id, names, context, limits, generator, examples, inventory, thread_id,
            exclude_example_tasks, session_class):
    Session = session_class
    from methods import telemetry
    from methods.chat_transcript import PlanChatTranscript, capture_transcript
    transcript = PlanChatTranscript()
    try:
        def binding(name, *args, **kwargs):
            return _rpc(connection, name, args, kwargs, session.current_call)
        bindings = {name: partial(binding, name) for name in names}
        def emit(kind, value):
            connection.send(("event", kind, serialize(value)))
        with capture_transcript(transcript), telemetry.thread(thread_id=thread_id):
            session = Session(episode_id, bindings, context, limits, generator, emit, examples, inventory,
                              context_query=lambda: _rpc(connection, "observation_context", (), {}, session.current_call),
                              exclude_example_tasks=exclude_example_tasks)
            result = session.policy(task)
            import json
            if len(json.dumps(serialize(result)).encode()) > limits.max_output_bytes:
                raise ValueError("output_size_limit")
        connection.send(("done", serialize(result), serialize(session.budget.counts)))
    except BaseException as error:
        connection.send(("failed", f"{type(error).__name__}: {error}", traceback.format_exc()))
    finally:
        connection.send(("chat", transcript.messages))
        connection.close()


class PolicyRuntime:
    """Supervises one episode's worker. Subclasses set the method's session class
    (importable at module level, so the spawned worker can load it) and labels."""
    session_class = None
    observation_label = "LMP observation"
    action_span, query_span = "lmp_action", "lmp_query"

    def __init__(self, adapter, limits=None, generator=None):
        if self.session_class is None:
            raise TypeError("PolicyRuntime subclasses must set session_class")
        self.adapter = adapter
        self.limits = limits or Limits()
        self.generator = generator
        self.events = []
        self.chat = []
        self.native_pending = False

    def run(self, task, examples="", inventory=(), thread_id="lmp", *, exclude_example_tasks=()):
        from .lmp_environment import ACTION_CLASSES
        from methods import telemetry
        from methods.chat_transcript import append_message, record_request, record_response
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe()
        process = ctx.Process(target=_worker, args=(child, task, self.adapter.episode_id,
                    tuple(self.adapter.registry), self.adapter.context(), self.limits,
                    self.generator, examples, inventory, thread_id, tuple(exclude_example_tasks),
                    self.session_class))
        budget = Budget(self.limits)
        outcome = {"status": "execution_failed", "error": "worker_exited"}
        process.start()
        child.close()
        try:
            finished = False
            while not finished:
                budget.check()
                if not parent.poll(min(.02, max(0, budget.deadline - time.monotonic()))):
                    if not process.is_alive():
                        break
                    continue
                message = parent.recv()
                kind = message[0]
                if kind == "event":
                    self.events.append({"kind": message[1], **message[2]})
                    if message[1] == "generation_request":
                        budget.consume("model_requests")
                        record_request(message[2]["prompt"], message[2]["purpose"])
                    elif message[1] == "generation":
                        # The transcript keeps what the model sent, fences included.
                        record_response(message[2].get("raw_source", message[2]["source"]), message[2]["purpose"])
                elif kind == "rpc":
                    _, name, args, kwargs, call_id = message
                    if name not in self.adapter.registry and name != "observation_context":
                        raise ValueError("unknown_rpc")
                    action = name in ACTION_CLASSES
                    budget.consume("actions" if action else "queries")
                    started = time.monotonic()
                    output = Queue(maxsize=1)
                    # A native call cannot be safely interrupted. Keep it in the
                    # parent; on deadline poison the episode and abort the run.
                    def invoke():
                        try:
                            with telemetry.thread(thread_id=thread_id):
                                function = self.adapter.context if name == "observation_context" else self.adapter.registry[name]
                                with telemetry.span(self.action_span if action else self.query_span,
                                                    {"name": name, "arguments": serialize(args)}) as trace:
                                    value = function(*args, **kwargs)
                                    trace.update(result=serialize(value), observation_revision=self.adapter.revision)
                                    output.put(("ok", value))
                        except BaseException as error:
                            output.put(("error", f"{type(error).__name__}: {error}"))
                    self.native_pending = action
                    Thread(target=copy_context().run, args=(invoke,), daemon=True).start()
                    try:
                        response = output.get(timeout=max(0, budget.deadline - time.monotonic()))
                    except Empty:
                        if action:
                            env = self.adapter.env
                            env.execution_failed = env.native_state_uncertain = True
                        raise TimeoutError("native_action_deadline" if action else "query_deadline")
                    self.native_pending = False
                    budget.check()
                    event = {"kind": "action" if action else "query", "name": name,
                             "arguments": serialize(args), "keywords": serialize(kwargs),
                             "result": serialize(response[1]), "status": response[0],
                             "episode_id": self.adapter.episode_id,
                             "parent_call_id": call_id,
                             "observation_revision": self.adapter.revision,
                             "elapsed_seconds": time.monotonic() - started}
                    self.events.append(event)
                    append_message("user", self.observation_label + ": " + str(event))
                    parent.send(response)
                    if self.adapter.env.native_state_uncertain:
                        raise RuntimeError("uncertain_native_state")
                elif kind == "done":
                    outcome = {"status": "executed", "result": message[1], "generation_counts": message[2], "error": None}
                elif kind == "failed":
                    outcome = {"status": "execution_failed", "error": message[1], "traceback": message[2]}
                elif kind == "chat":
                    self.chat = message[1]
                    finished = True
        except (Exception, EOFError) as error:
            outcome = {"status": "execution_failed", "error": f"{type(error).__name__}: {error}"}
        finally:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
        outcome.update(counts=budget.counts, events=self.events, limits=asdict(self.limits),
                       final_state_available=not (self.native_pending or self.adapter.env.native_state_uncertain))
        return outcome
