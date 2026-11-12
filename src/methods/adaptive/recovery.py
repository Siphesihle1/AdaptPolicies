"""The recovery ladder (D5): local recovery, helper regeneration, continuation replan.

Each failure first gets up to `max_recoveries_per_checkpoint` local recoveries at
its site. Then the innermost generated helper on the call stack that still has
regenerations left is regenerated and called again; when none is left the
running policy is replaced by a continuation policy. A failure that recurs after
a replan without any successful action in between ends the episode.
"""

import ast
from collections import Counter
from uuid import uuid4

from .checkpoints import NoProgress, RegenerateHelper, Replan, exception_text, is_terminal, recover_filename
from .progress import bindings_section, failure_section, program_section, progress_section


class LocalOutcome:
    def __init__(self, ran, value=None, error=None):
        self.ran, self.value, self.error = ran, value, error


class RecoveryController:
    def __init__(self, session):
        self.session = session
        self.limits = session.limits
        self.local_attempts = Counter()
        self.regenerations = Counter()
        self.replans = 0
        self.history = []  # model-facing summaries of earlier recoveries
        self.seen = {}  # failure signature -> (successful actions, replans) when last seen

    # Entry points -----------------------------------------------------------

    def recover_checkpoint(self, failure, check):
        def attempt(_):
            value = check()
            return bool(value), value
        return self.handle(failure, attempt)

    def recover_action(self, failure, original, retry):
        from dataclasses import replace

        def attempt(returned):
            if returned is True:
                # The recovery reports that the action's effect already holds.
                return True, replace(original, status="succeeded", error=None, recovered=True)
            result = retry()
            if result.status == "succeeded":
                return True, replace(result, recovered=True)
            return False, result
        return self.handle(failure, attempt)

    def recover_exception(self, failure):
        # The failed helper call has unwound; a recovery that runs to completion
        # stands in for it and its return value becomes the call's result.
        return self.handle(failure, lambda returned: (True, returned))

    # Ladder -----------------------------------------------------------------

    def handle(self, failure, attempt):
        self.note(failure)
        site = failure.site
        while self.local_attempts[site] < self.limits.max_recoveries_per_checkpoint:
            self.local_attempts[site] += 1
            outcome = self.local(failure)
            if outcome.ran:
                succeeded, value = attempt(outcome.value)
                self.finish("local", failure, succeeded, None if succeeded else "condition still fails")
                if succeeded:
                    return value
            else:
                self.finish("local", failure, False, outcome.error)
        self.escalate(failure)

    def note(self, failure):
        session = self.session
        signature = failure.signature()
        progress = (session.successful_actions, self.replans)
        previous = self.seen.get(signature)
        session.emit("checkpoint_failed", {**failure.record(), "parent_call_id": session.current_call})
        if previous is not None and previous[0] == session.successful_actions and self.replans > previous[1]:
            session.emit("terminated_no_progress", {**failure.record(), "parent_call_id": session.current_call})
            raise NoProgress(failure)
        self.seen[signature] = progress

    def finish(self, scope, failure, succeeded, error):
        self.history.append({"scope": scope, "failure": failure.short(), "succeeded": succeeded, "error": error})
        self.session.emit("recovery_result", {"scope": scope, "trigger": failure.trigger, "succeeded": succeeded,
                                              "failure": failure.summary(), "error": error,
                                              "parent_call_id": self.session.current_call})

    def escalate(self, failure):
        for frame in failure.frames:
            if frame.kind != "helper" or self.regenerations[frame.helper] >= self.limits.max_recoveries_per_checkpoint:
                continue
            self.regenerations[frame.helper] += 1
            error = self.regenerate(frame.helper, failure)
            self.finish("helper", failure, error is None, error)
            if error is None:
                raise RegenerateHelper(frame.helper)
        raise Replan(failure)

    # Scopes -----------------------------------------------------------------

    def context(self, failure, bindings=True):
        session = self.session
        sections = {"program": program_section(session.running_sources(), failure),
                    "failure": failure_section(failure),
                    "progress": progress_section(session.trace, self.history)}
        if bindings:
            sections["bindings"] = bindings_section(failure.bindings)
        return sections

    def generate(self, purpose, query, failure, bindings=True):
        session = self.session
        session.failure_context = self.context(failure, bindings)
        try:
            return session.generate(purpose, query, session.context_query(), str(uuid4()))
        finally:
            session.failure_context = None

    def local(self, failure):
        """Generate and run recover() from the current state."""
        session = self.session
        number = len(self.history) + 1
        source = self.generate(session.purposes["recover"], "Recover from the failure below.", failure)
        session.emit("recovery_generated", {"scope": "local", "source": source, "trigger": failure.trigger,
                                            "parent_call_id": session.current_call})
        try:
            reserved = session.reserved | set(failure.bindings)
            tree = session.validate(source, reserved)
            check_entry(tree, "recover")
            if any(isinstance(node, ast.Name) and node.id == "checkpoint" for node in ast.walk(tree)):
                raise ValueError("recover must not call checkpoint")
            session.functions.resolve(source)
            session.install_new_helpers()
        except Exception as error:
            if is_terminal(error):
                raise
            return LocalOutcome(False, error=exception_text(error))
        namespace = dict(session.namespace)
        namespace.update(failure.bindings)
        session.recovering += 1
        try:
            exec(compile(source, recover_filename(number), "exec"), namespace, namespace)
            return LocalOutcome(True, namespace["recover"]())
        except Exception as error:
            if is_terminal(error):
                raise
            return LocalOutcome(False, error=exception_text(error))
        finally:
            session.recovering -= 1

    def regenerate(self, name, failure):
        """Replace a generated helper; returns an error text when that fails."""
        session = self.session
        old = session.functions.sources.get(name, "")
        query = f"Rewrite helper {name} so that it handles the failure.\nFailing helper:\n{old}"
        source = self.generate(session.purposes["function"], query, failure, bindings=False)
        session.emit("helper_regenerated", {"name": name, "source": source, "previous_source": old,
                                            "parent_call_id": session.current_call})
        try:
            tree = session.validate(source, session.reserved)
            if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.body[0].name != name:
                raise ValueError("Regenerated helper must contain exactly its own definition")
            old_tree = ast.parse(old) if old else None
            if old_tree and ast.dump(old_tree.body[0].args) != ast.dump(tree.body[0].args):
                raise ValueError("Regenerated helper must keep its parameters")
            session.functions.sources[name] = source
            session.functions.resolve(source)
            session.install_helper(name, source)
            session.install_new_helpers()
        except Exception as error:
            if is_terminal(error):
                raise
            if old:
                session.functions.sources[name] = old
            return exception_text(error)
        return None

    def replan(self, failure, task):
        """Generate a continuation policy from the current state."""
        session = self.session
        self.replans += 1
        source = self.generate(session.purposes["replan"], task, failure, bindings=False)
        session.emit("replan", {"number": self.replans, "source": source, "failure": failure.record(),
                                "parent_call_id": session.current_call})
        self.history.append({"scope": "replan", "failure": failure.short(), "succeeded": True, "error": None})
        return source


def check_entry(tree, name):
    """Module scope holds function definitions only, including a zero-argument entry point."""
    if not tree.body or any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError(f"{name} output must contain function definitions only")
    entries = [node for node in tree.body if node.name == name]
    if len(entries) != 1 or entries[0].args.args or entries[0].args.posonlyargs or entries[0].args.kwonlyargs \
            or entries[0].args.vararg or entries[0].args.kwarg:
        raise ValueError(f"Missing zero-argument {name}() entry point")

