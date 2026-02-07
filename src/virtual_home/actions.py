from abc import ABC, abstractmethod
from random import choice
from .environment import VHEnvironment
from .task import VHTask
from .virtualhome_types import ObjectClassName


class Action(ABC):
    def __init__(self, env: VHEnvironment, task: VHTask):
        self.env = env
        self.task = task
        self.action_name = ""

    def run(self, *objs: str):
        if self.action_name != "assert":
            self.task.total_steps += 1

        omit_action = any(
            self.action_name == action[0] and objs == action[1:]
            for action in self.env.actions_to_omit
        )

        if self.task.terminate_current_subtask or omit_action:
            return None

        return self.action(*objs)

    @abstractmethod
    def action(self, *objs: str) -> bool | None: ...


# Two argument actions
class PutIn(Action):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "putin"

    def __call__(self, obj: ObjectClassName, receptable: ObjectClassName):
        super().run(obj, receptable)

    def action(self, *objs: str):
        (obj, receptacle) = objs
        self.env.last_action = (self.action_name, *objs)
        obj_ids = [
            id for id in self.env.find_obj(obj) if id in self.env.agent_has_objid
        ]
        receptable_ids = self.env.find_obj(receptacle)

        if len(obj_ids) == 0:
            self.env.log_file.write(f"Object {obj} not in hand\n")
            return False

        if len(receptable_ids) == 0:
            self.env.log_file.write(f"Object {obj} not found\n")
            return False

        obj_id = obj_ids[0] if len(obj_ids) == 1 else choice(obj_ids)
        receptable_id = (
            receptable_ids[0]
            if len(receptable_ids) == 1
            else (
                self.env.found_id
                if self.env.found_id in receptable_ids
                else choice(receptable_ids)
            )
        )

        return self.env.execute(
            f"<char0> [{self.action_name}] <{obj}> ({obj_id}) <{receptacle}> ({receptable_id})"
        )


class PutBack(PutIn):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "putback"


# One argument actions
class Find(Action):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "find"

    def __call__(self, obj: ObjectClassName):
        super().run(obj)

    def action(self, *objs: str):
        (obj,) = objs
        self.env.last_action = (self.action_name, *objs)
        obj_ids = self.env.find_obj(obj)

        if len(obj_ids) == 0:
            self.env.log_file.write(f"Object {obj} not found\n")
            return False

        obj_id = self.env.found_id = choice(obj_ids)

        return self.env.execute(f"<char0> [{self.action_name}] <{obj}> ({obj_id})")


class Walk(Find):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "walk"


class Open(Find):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "open"

    def action(self, *objs: str):
        (obj,) = objs
        self.env.last_action = (self.action_name, *objs)
        obj_ids = self.env.find_obj(obj)

        if len(obj_ids) == 0:
            self.env.log_file.write(f"Object {obj} not found\n")
            return False

        obj_id = (
            obj_ids[0]
            if len(obj_ids) == 1
            else (
                self.env.found_id if self.env.found_id in obj_ids else choice(obj_ids)
            )
        )

        return self.env.execute(f"<char0> [{self.action_name}] <{obj}> ({obj_id})")


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
class TurnRight(Action):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "turnright"

    def __call__(self):
        super().run()

    def action(self, *_: str):
        return self.env.execute(f"<char0> [{self.action_name}]")


class TurnLeft(TurnRight):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "turnleft"


class WalkForward(TurnRight):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "walkforward"


class StandUp(TurnRight):
    def __init__(self, env: VHEnvironment, task: VHTask):
        super().__init__(env, task)
        self.action_name = "standup"
