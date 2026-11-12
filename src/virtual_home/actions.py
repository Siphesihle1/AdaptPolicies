from abc import ABC, abstractmethod
from collections.abc import Iterable
from methods import telemetry as weave
from .environment import VHEnvironment
from .graph_query import N
from .task import VHTask
from .virtualhome_types import ObjectClassName, ObjectRef, validate_object_ref


class Action(ABC):
    def __init__(self, env: VHEnvironment, task: VHTask):
        self.env = env
        self.task = task
        self.action_name = ""

    def resolve_object(self, name: str, held_only: bool = False) -> int | None:
        if isinstance(name, ObjectRef):
            validate_object_ref(name, self.env)
            if held_only and name.id not in self.env.obj_ids_in_hand:
                self.env.last_action_error = f"Object {name.name} ({name.id}) not in hand"
                return None
            return name.id
        nearest_in_room = self.env.find_obj(name)
        candidates = (
            N(self.env.graph).class_name(name).select("id")
            if hasattr(self.env, "graph")
            else nearest_in_room
        )
        held = [
            identifier
            for identifier in candidates
            if identifier in self.env.obj_ids_in_hand
        ]
        bindings = getattr(self.env, "object_bindings", {})
        if held_only:
            candidates = held
        if not candidates:
            message = f"Object {name} {'not in hand' if held_only else 'not found'}"
            self.env.log_file.write(message + "\n")
            self.env.last_action_error = message
            return None
        eligible = held or candidates
        bound = bindings.get(name)
        previous = getattr(self.env, "found_id", None)
        close = set(getattr(self.env, "obj_ids_close", []))
        distances = getattr(self.env, "object_distances", {})

        def nearest(identifiers: Iterable[int]) -> int:
            return min(
                identifiers,
                key=lambda identifier: (
                    distances.get(identifier, float("inf")),
                    identifier,
                ),
            )

        if bound in eligible:
            identifier, reason = bound, "bound"
        elif held:
            identifier, reason = min(held), "held"
        elif previous in eligible:
            identifier, reason = previous, "last_find"
        elif close.intersection(eligible):
            identifier, reason = nearest(close.intersection(eligible)), "close"
        elif set(nearest_in_room).intersection(eligible):
            identifier, reason = (
                nearest(set(nearest_in_room).intersection(eligible)),
                "nearest_in_room",
            )
        else:
            identifier, reason = nearest(eligible), "eligible"
        self.env.log_file.write(
            f"resolve {self.action_name} {name}: candidates={sorted(candidates)}, selected={identifier}, reason={reason}, squared_distance={distances.get(identifier)}\n"
        )
        return identifier

    def execute(self, *objects: tuple[str, int]) -> bool:
        objects = tuple((name.name if isinstance(name, ObjectRef) else name, identifier)
                        for name, identifier in objects)
        arguments = " ".join(f"<{name}> ({identifier})" for name, identifier in objects)
        success = self.env.execute(f"<char0> [{self.action_name}] {arguments}")
        if success:
            if not hasattr(self.env, "object_bindings"):
                self.env.object_bindings = {}
            self.env.object_bindings.update(objects)
        return success

    def run(self, *objs: str) -> bool | None:
        with weave.thread(thread_id=self.task.thread_id), weave.attributes(
            {
                "task_instruction": self.task.task_instruction,
                "subtask": self.task.current_subtask,
            }
        ), weave.span(
            "plan_action", {"action": self.action_name, "objects": list(objs)}
        ) as output:
            return self._run(objs, output)

    def _run(self, objs: tuple[str, ...], output: dict[str, object]) -> bool | None:
        if self.action_name != "assert":
            self.task.total_steps += 1

        omit_action = any(
            self.action_name == action[0]
            and all((obj1.name if isinstance(obj1, ObjectRef) else obj1) == obj2
                    for (obj1, obj2) in zip(objs, action[1:]))
            for action in self.env.actions_to_omit
        )

        if (
            self.env.execution_failed
            or self.task.terminate_current_subtask
            or omit_action
        ):
            output.update(
                status="skipped",
                reason=(
                    "previous_unity_failure"
                    if self.env.execution_failed
                    else (
                        "subtask_terminated"
                        if self.task.terminate_current_subtask
                        else "omitted_action"
                    )
                ),
            )
            return None

        self.env.last_action_error = None
        result = self.action(*objs)
        if result is False and not self.env.last_action_error:
            self.env.last_action_error = f"{self.action_name} could not be executed"
        output.update(
            result=result,
            status=(
                "succeeded"
                if result is True
                else "failed" if result is False else "unknown"
            ),
        )
        return result

    @abstractmethod
    def action(self, *objs: str) -> bool | None: ...


# Two argument actions
class PutIn(Action):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "putin"

    def __call__(self, obj: ObjectClassName, receptable: ObjectClassName):
        return super().run(obj, receptable)

    def action(self, *objs: str) -> bool:
        obj, receptacle = objs
        self.env.last_action = (self.action_name, *objs)
        obj_id = self.resolve_object(obj, held_only=True)
        receptacle_id = self.resolve_object(receptacle)
        if obj_id is None or receptacle_id is None:
            return False
        return self.execute((obj, obj_id), (receptacle, receptacle_id))


class PutBack(PutIn):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "putback"


class Apply(PutIn):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "apply"


# One argument actions
class Find(Action):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "find"

    def __call__(self, obj: ObjectClassName):
        return super().run(obj)

    def action(self, *objs: str) -> bool:
        (obj,) = objs
        self.env.last_action = (self.action_name, *objs)
        obj_id = self.resolve_object(obj)
        if obj_id is None:
            return False
        success = self.execute((obj, obj_id))
        if success:
            self.env.found_id = obj_id
        return success


class Walk(Find):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "walk"


class Open(Find):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "open"

    def action(self, *objs: str) -> bool:
        (obj,) = objs
        self.env.last_action = (self.action_name, *objs)
        obj_id = self.resolve_object(obj)
        if obj_id is None:
            return False
        return self.execute((obj, obj_id))


class Run(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "run"


class Close(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "close"


class Drink(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "drink"


class Grab(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "grab"


class LookAt(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "lookat"


class Touch(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "touch"


class Talk(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "talk"

    def action(self, *objs: str) -> bool:
        (obj,) = objs
        self.env.last_action = (self.action_name, obj)
        identifier = self.resolve_object(obj, held_only=True)
        if identifier is None:
            return False
        return self.execute((obj, identifier))


class Read(Talk):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "read"


class Fold(Talk):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "fold"


class Unfold(Fold):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "unfold"


class Use(Talk):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "use"


class SwitchOff(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "switchoff"


class SwitchOn(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "switchon"


class Sit(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "sit"


class TurnTo(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "turnto"


class PointAt(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "pointat"


class Watch(Open):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "watch"


# Zero argument actions
class StandUp(Action):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "standup"

    def __call__(self):
        return super().run()

    def action(self, *_: str):
        return self.env.execute(f"<char0> [{self.action_name}]")
