"""The Adaptive Policies session: CaP's LMP session with checkpoints and recovery.

Generated policies and helpers run in one persistent namespace. Trusted wrappers
around actions and helpers, and the `checkpoint` function, notice failures and
hand them to the recovery ladder; execution then continues after the failure.
"""

import ast
import sys
from uuid import uuid4

from methods.shared.lmp_environment import ACTION_CLASSES
from methods.shared.lmp_runtime import validate
from methods.shared.lmp_session import Session
from . import prompt
from .checkpoints import (Failure, NoProgress, RegenerateHelper, Replan, bindings_of, caller_frame,
                          exception_text, generated_frames, helper_filename, is_terminal, policy_filename,
                          traceback_frames)
from .environment import AP_ATTRIBUTES
from .recovery import RecoveryController, check_entry
from .settings import PURPOSES


class AdaptiveSession(Session):
    purposes = PURPOSES
    attributes = AP_ATTRIBUTES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failure_context = None
        self.trace = []  # actions and passed checkpoints, for the progress section
        self.successful_actions = 0
        self.recovering = 0  # recovery code runs without nested recovery
        self.policy_version = 0
        self.policy_source = None
        self.helper_versions = {}
        self.installed = {}  # helper name -> installed source
        self.helper_impls = {}
        self.sources_by_file = {}
        self.task = None
        for name in ACTION_CLASSES:
            if name in self.namespace:
                self.namespace[name] = self.action_binding(name, self.namespace[name])
        if self.limits.explicit:
            self.namespace["checkpoint"] = self.checkpoint
        # Reserved in every condition so generated code cannot define its own.
        self.reserved = self.reserved | {"checkpoint"}
        self.recovery = RecoveryController(self)

    # Prompts and validation -------------------------------------------------

    def build_prompt(self, episode_id, purpose, query, context=None, examples="", inventory=(), exclude_tasks=()):
        return prompt.build_prompt(episode_id, purpose, query, context, examples, inventory, exclude_tasks,
                                   placement=self.limits.placement, failure=self.failure_context)

    def validate(self, source, reserved=None):
        tree = validate(source, self.reserved if reserved is None else reserved,
                        self.limits.max_source_bytes, self.attributes)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                raise ValueError("Bare except clauses are forbidden")
        return tree

    # Program installation ---------------------------------------------------

    def install_policy(self, source, program):
        """Validate, resolve helpers and define a policy version (initial or replan)."""
        tree = self.validate(source)
        check_entry(tree, "policy")
        self.emit("code_validation", {"code_valid": True, "program": program, "parent_call_id": self.current_call})
        self.functions.resolve(source)
        self.emit("validated", {"code_valid": True, "dependencies_resolved": True, "program": program,
                                "parent_call_id": self.current_call})
        self.install_new_helpers()
        self.policy_version += 1
        filename = policy_filename(self.policy_version)
        local = {}
        exec(compile(source, filename, "exec"), self.namespace, local)
        # Helpers the policy defines itself get the same wrappers as generated ones.
        for name, value in local.items():
            if name != "policy":
                definition = next(node for node in tree.body if node.name == name)
                self.functions.sources[name] = ast.get_source_segment(source, definition)
                self.install_helper(name, self.functions.sources[name])
        self.namespace["policy"] = local["policy"]
        self.policy_source = source
        self.sources_by_file = {k: v for k, v in self.sources_by_file.items() if not k.startswith("<ap-policy:")}
        self.sources_by_file[filename] = ("policy", source)

    def install_new_helpers(self):
        for name, source in list(self.functions.sources.items()):
            if self.installed.get(name) != source:
                self.install_helper(name, source)

    def install_helper(self, name, source):
        version = self.helper_versions.get(name, 0) + 1
        self.helper_versions[name] = version
        filename = helper_filename(name, version)
        local = {}
        exec(compile(source, filename, "exec"), self.namespace, local)
        self.helper_impls[name] = local[name]
        self.installed[name] = source
        self.sources_by_file = {k: v for k, v in self.sources_by_file.items()
                                if not k.startswith(f"<ap-helper:{name}:")}
        self.sources_by_file[filename] = (f"helper {name}", source)
        if name not in self.namespace or not getattr(self.namespace[name], "ap_helper", False):
            self.namespace[name] = self.helper_binding(name)

    def running_sources(self):
        """Current policy first, then current helpers, keyed by generated filename."""
        policy = {k: v for k, v in self.sources_by_file.items() if k.startswith("<ap-policy:")}
        helpers = {k: v for k, v in self.sources_by_file.items() if k.startswith("<ap-helper:")}
        return {**policy, **dict(sorted(helpers.items()))}

    # Trusted wrappers -------------------------------------------------------

    def action_binding(self, name, raw):
        def action(*args, **kwargs):
            result = self.record_action(name, args, raw(*args, **kwargs))
            if result.status != "failed" or not self.limits.implicit or self.recovering:
                return result
            caller = caller_frame(sys._getframe(1))
            failure = Failure("action", generated_frames(caller), bindings_of(caller), action=name,
                              arguments=args, message=result.message)
            recovered = self.recovery.recover_action(
                failure, result, lambda: self.record_action(name, args, raw(*args, **kwargs)))
            self.record_recovered(name, args, recovered)
            return recovered
        return action

    def record_action(self, name, args, result):
        from .checkpoints import describe
        self.trace.append({"kind": "action", "call": f"{name}({', '.join(describe(a) for a in args)})",
                           "status": result.status, "message": getattr(result, "message", None)})
        if result.status == "succeeded":
            self.successful_actions += 1
        return result

    def record_recovered(self, name, args, result):
        from .checkpoints import describe
        self.trace.append({"kind": "action", "call": f"{name}({', '.join(describe(a) for a in args)})",
                           "status": result.status, "recovered": True})

    def checkpoint(self, description, check):
        if not isinstance(description, str) or not callable(check):
            raise TypeError("checkpoint(description, check) needs a description and a zero-argument callable")
        self.budget.check()
        self.emit("checkpoint_reached", {"description": description, "parent_call_id": self.current_call})
        value = check()
        if value:
            self.trace.append({"kind": "checkpoint", "description": description})
            self.emit("checkpoint_passed", {"description": description, "parent_call_id": self.current_call})
            return value
        if self.recovering:
            return value
        caller = caller_frame(sys._getframe(1))
        failure = Failure("checkpoint", generated_frames(caller), bindings_of(caller), description=description,
                          check_source=self.check_source(check))
        return self.recovery.recover_checkpoint(failure, check)

    def check_source(self, check):
        code = getattr(check, "__code__", None)
        if code is None:
            return repr(check)
        source = self.sources_by_file.get(code.co_filename, (None, ""))[1]
        lines = source.splitlines()
        if 0 < code.co_firstlineno <= len(lines):
            line = lines[code.co_firstlineno - 1].strip()
            text = line[line.find("lambda"):] if "lambda" in line else line
            # Drop the closing parentheses of the enclosing checkpoint(...) call.
            while text.endswith(")") and text.count(")") > text.count("("):
                text = text[:-1]
            return text
        return code.co_name

    def helper_binding(self, name):
        def helper(*args, **kwargs):
            self.emit("helper_call", {"name": name, "version": self.helper_versions[name],
                                      "parent_call_id": self.current_call})
            while True:
                try:
                    return self.helper_impls[name](*args, **kwargs)
                except RegenerateHelper as signal:
                    if signal.name != name:
                        raise
                    continue  # call the regenerated version with the same arguments
                except Exception as error:
                    if self.recovering or is_terminal(error):
                        raise
                    frames, innermost = traceback_frames(error.__traceback__)
                    failure = Failure("exception", frames, bindings_of(innermost),
                                      exception=exception_text(error))
                    try:
                        return self.recovery.recover_exception(failure)
                    except RegenerateHelper as signal:
                        if signal.name != name:
                            raise
        helper.ap_helper = True
        helper.__name__ = name
        return helper

    # Episode ----------------------------------------------------------------

    def policy(self, task):
        self.task = task
        call_id = str(uuid4())
        source = self.generate(self.purposes["policy"], task, self.context, call_id)
        self.current_call = call_id
        self.emit("policy", {"source": source})
        self.install_policy(source, "policy")
        while True:
            try:
                return self.namespace["policy"]()
            except Replan as signal:
                failure = signal.failure
            except NoProgress:
                raise
            except Exception as error:
                if is_terminal(error):
                    raise
                # An exception in policy() itself goes straight to a replan.
                frames, innermost = traceback_frames(error.__traceback__)
                failure = Failure("exception", frames, bindings_of(innermost), exception=exception_text(error))
                self.recovery.note(failure)
            source = self.recovery.replan(failure, task)
            self.install_policy(source, "replan")
