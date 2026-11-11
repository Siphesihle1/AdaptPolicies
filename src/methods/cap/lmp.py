"""Language model programs and one-episode shared helper/session namespace."""

import ast
import time
from uuid import uuid4
from virtual_home.virtualhome_types import ObjectRef
from .function_gen import FunctionGenerator
from .runtime import Budget, BUILTINS, validate, serialize
from .prompt import build_prompt


class Session:
    def __init__(self, episode_id, bindings, context, limits, generator=None,
                 emit=lambda *args: None, examples="", inventory=(), context_query=None):
        self.episode_id, self.limits = episode_id, limits
        self.context = context
        self.context_query = context_query or (lambda: context)
        self.budget = Budget(limits)
        self.emit = emit
        self.generator = generator
        self.examples, self.inventory = examples, inventory
        self.current_call = None
        self.nesting = 0
        self.namespace = {"__builtins__": BUILTINS, **bindings,
                          "parse_objects": self.parse_objects, "parse_question": self.parse_question}
        self.reserved = set(bindings) | set(BUILTINS) | {"parse_objects", "parse_question"}
        self.functions = FunctionGenerator(self)

    def generate(self, purpose, query, context=None, call_id=None):
        self.budget.consume("model_requests")
        prompt = build_prompt(self.episode_id, purpose, query, context,
                              self.examples if purpose == "cap_policy" else "", self.inventory)
        call_id = call_id or str(uuid4())
        parent = self.current_call
        started = time.monotonic()
        self.emit("generation_request", {"call_id": call_id, "parent_call_id": parent,
                  "purpose": purpose, "prompt": prompt, "episode_id": self.episode_id})
        from methods.chat_transcript import record_request, record_response
        try:
            if self.generator is None:
                from methods.llm import generate
                from methods.generation_metrics import capture_completions
                with capture_completions(lambda row: self.emit("generation_metrics", {**row, "call_id": call_id})):
                    source = generate(prompt, purpose=purpose)
            else:
                record_request(prompt, purpose)
                source = self.generator(prompt, purpose)
            self.budget.check()
            if not isinstance(source, str) or len(source.encode()) > self.limits.max_source_bytes:
                raise ValueError("source_size_limit")
            if self.generator is not None:
                record_response(source, purpose)
            self.emit("generation", {"call_id": call_id, "parent_call_id": parent,
                      "purpose": purpose, "source": source,
                      "elapsed_seconds": time.monotonic() - started})
            return source
        except BaseException as error:
            self.emit("generation_error", {"call_id": call_id, "parent_call_id": parent,
                      "purpose": purpose, "error": str(error), "elapsed_seconds": time.monotonic()-started})
            raise

    def execute(self, source, result_name=None, policy=False):
        tree = validate(source, self.reserved, self.limits.max_source_bytes)
        if policy:
            if not tree.body or any(not isinstance(n, ast.FunctionDef) for n in tree.body):
                raise ValueError("Policy output must contain function definitions only")
            definitions = [n for n in tree.body if n.name == "policy"]
            if len(definitions) != 1 or definitions[0].args.args or definitions[0].args.posonlyargs or definitions[0].args.kwonlyargs:
                raise ValueError("Missing zero-argument policy() entry point")
        self.emit("code_validation", {"code_valid": True, "program": "policy" if policy else "specialized",
                                      "parent_call_id": self.current_call})
        self.functions.resolve(source)
        self.emit("validated", {"code_valid": True, "dependencies_resolved": True,
                               "program": "policy" if policy else "specialized",
                               "parent_call_id": self.current_call})
        namespace = dict(self.namespace)
        for helper in self.functions.sources.values():
            exec(compile(helper, "<cap-helper>", "exec"), namespace, namespace)
        exec(compile(source, "<cap-program>", "exec"), namespace, namespace)
        if policy:
            return namespace["policy"]()
        if result_name not in namespace:
            raise ValueError("missing_return_value: " + str(result_name))
        return namespace[result_name]

    def policy(self, task):
        call_id = str(uuid4())
        source = self.generate("cap_policy", task, self.context, call_id)
        self.current_call = call_id
        self.emit("policy", {"source": source})
        return self.execute(source, policy=True)

    def specialized(self, purpose, query):
        self.budget.check()
        self.nesting += 1
        if self.nesting > self.limits.max_depth:
            raise RuntimeError("nested_lmp_depth_limit")
        previous = self.current_call
        call_id = str(uuid4())
        try:
            context = self.context_query()
            source = self.generate(purpose, str(query), context, call_id)
            self.current_call = call_id
            result = self.execute(source, "ret_val")
            encoded = serialize(result)
            import json
            if len(json.dumps(encoded).encode()) > self.limits.max_output_bytes:
                raise ValueError("output_size_limit")
            if purpose == "cap_objects":
                visible = context["visible_objects"]
                if not isinstance(result, list) or any(not isinstance(obj, ObjectRef) or obj not in visible for obj in result):
                    raise ValueError("invalid_object_result")
            else:
                self.validate_references(result, context["visible_objects"])
            self.emit("lmp_result", {"purpose": purpose, "call_id": self.current_call,
                      "parent_call_id": previous, "result": encoded})
            return result
        finally:
            self.current_call = previous
            self.nesting -= 1

    def validate_references(self, result, visible):
        if isinstance(result, ObjectRef) and result not in visible:
            raise ValueError("invalid_object_result")
        if isinstance(result, dict):
            for item in list(result.keys()) + list(result.values()):
                self.validate_references(item, visible)
        elif isinstance(result, (list, tuple, set, frozenset)):
            for item in result:
                self.validate_references(item, visible)

    def parse_objects(self, description):
        return self.specialized("cap_objects", description)

    def parse_question(self, question):
        return self.specialized("cap_question", question)


class LMP:
    """Named callable facade for specialized programs."""
    def __init__(self, session, purpose):
        self.session, self.purpose = session, purpose

    def __call__(self, query):
        return self.session.policy(query) if self.purpose == "cap_policy" else self.session.specialized(self.purpose, query)
