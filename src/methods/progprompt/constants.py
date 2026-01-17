from typing import Callable


CURRENT_STATE_PROMPT = "kitchencounterdrawer, door is OPEN, character, wallpictureframe, clothespile is CLOSED, coffeemaker is OFF, pie, wall, bedroom, microwave is OFF and CLOSED, lightswitch is ON, kitchencabinet is CLOSED, washingsponge, bellpepper, salmon, fridge is CLOSED, wallshelf, tvstand, paper, floor, chips, photoframe, kitchen, whippedcream, candybar, faucet is OFF, tv is OFF, cereal, stovefan, waterglass, cutleryknife, kitchentable, condimentbottle, wineglass, bookshelf, cutleryfork, chocolatesyrup, walllamp, bench, sink, crackers, orchid, condimentshaker, kitchencounter is CLOSED, livingroom, powersocket, coffeepot is CLOSED, creamybuns, ceilinglamp, rug, book is CLOSED, plate, toaster is OFF, clock is OFF, wallphone is OFF, ceiling, fryingpan, box is CLOSED, dishbowl, bananas, breadslice, bathroom, garbagecan is CLOSED, stove is OFF and CLOSED, dishwashingliquid, plate ON kitchencounter, cutleryfork ON kitchentable, bookshelf ON floor, cutleryknife ON kitchentable, bellpepper ON kitchencounter, microwave ON kitchencounterdrawer, chocolatesyrup ON wallshelf, whippedcream ON rug, salmon ON microwave, orchid ON tvstand, wallpictureframe ON wall, bench ON floor, tvstand ON floor, book INSIDE bookshelf, bananas ON dishbowl, toaster ON kitchencounterdrawer, whippedcream ON kitchentable, dishbowl INSIDE bookshelf, fryingpan ON stove, rug ON kitchentable, coffeepot INSIDE coffeemaker, waterglass ON rug, dishwashingliquid ON kitchencounter, wallshelf ON wall, washingsponge ON kitchencounter, clothespile INSIDE bookshelf, bananas INSIDE bookshelf, box ON bookshelf, plate ON kitchentable, waterglass ON kitchentable, creamybuns ON wallshelf, breadslice INSIDE toaster, coffeemaker ON kitchencounterdrawer, chips ON wallshelf, book ON kitchentable, dishbowl ON bookshelf, pie ON kitchentable, wineglass ON tvstand, box ON tvstand, coffeepot ON kitchencounter, bellpepper ON kitchencounterdrawer, condimentshaker INSIDE bookshelf, coffeemaker ON kitchencounter, toaster ON kitchencounter, box INSIDE bookshelf, crackers ON wallshelf, character HOLDS_RH book, faucet ON kitchencounter, book ON rug, cereal ON wallshelf, plate INSIDE microwave, candybar ON wallshelf, condimentbottle INSIDE bookshelf, tv ON tvstand, microwave ON kitchencounter, paper INSIDE bookshelf, kitchencounterdrawer ON kitchencounter, fridge ON floor, photoframe ON tvstand, wallpictureframe ON wallpictureframe, bench ON rug, pie ON rug, kitchencounterdrawer ON kitchencounterdrawer, dishbowl ON kitchencounter.\n\nassert('close' to 'mug' )\nFalse\nassert('close' to 'microwave' )\nTrue\nassert('book' is 'closed' )\nTrue\nassert('lightswitch' is 'OFF')\nFalse\nassert('book' in 'bookshelf')\nTrue\nassert('book' in 'hands')\nTrue\nassert('cereal' on 'bookshelf')\nFalse"
ASSERT_PROMPT_PREAMBLE = """You are a character in a virtual home simulator.

Task: Evaluate assert statements using the given state (what you see)
Return 'True' or 'False' only

State facts are literal and complete.

OUTPUT FORMAT (MANDATORY):
- Output exactly ONE token.
- The token MUST be either:
  True
  False
- Do not include punctuation, explanation, whitespace, or newlines.
- Any other output is invalid.

<rules>
- assert('close' to A) is True if A is in the same immediate location as the character (you)
- assert(A on B) is True if "A ON B" exists in state
- assert(A in B) is True if "A INSIDE B" exists in state
- assert(A is 'closed' | 'open' | 'on' | 'off' | ...) checks object state with correposponding values CLOSED, OPEN, ON, OFF, ...
- "hands" means the character is holding the object (HOLDS_RH or HOLDS_LH)
</rules>

"""

MODEL = "deepseek-r1:32b"

MAX_STEPS = 10
INITIAL_ROOM = "kitchen"

IMPORTS = """
from methods.progprompt.actions import Assert
from virtual_home.actions import (
    PutIn, 
    PutBack, 
    Find, 
    Walk, 
    Open, 
    Run,
    Close,
    Drink,
    Grab,
    LookAt,
    WalkTowards,
    SwitchOff,
    SwitchOn,
    Sit,
    TurnTo,
    PointAt,
    Watch,
    TurnRight,
    TurnLeft,
    WalkForward,
    StandUp,
)
from methods.progprompt.environment import ProgPromptEnvironment
from virtual_home.task import VHTask

from .subtasks import SUBTASKS

"""

TASK_INIT: Callable[[str, int], str] = (
    lambda task_instruction, max_steps: f"""
task = VHTask("{task_instruction}", SUBTASKS, max_steps={max_steps})
"""
)

ENVIRONMENT_INIT: Callable[[int, str, str], str] = (
    lambda env_id, initial_room, log_file_prefix: f"""
log_file = open("{log_file_prefix}/task_logs.txt", "a")
env = ProgPromptEnvironment({env_id}, "{initial_room}", task, log_file)
"""
)

ACTION_INIT = """
assert_ = Assert(env, task)
putin = PutIn(env, task)
putback = PutBack(env, task)
find = Find(env, task)
walk = Walk(env, task)
open = Open(env, task)
run = Run(env, task)
close = Close(env, task)
drink = Drink(env, task)
grab = Grab(env, task)
lookat = LookAt(env, task)
walktowards = WalkTowards(env, task)
switchoff = SwitchOff(env, task)
switchon = SwitchOn(env, task)
sit = Sit(env, task)
turnto = TurnTo(env, task)
pointat = PointAt(env, task)
watch = Watch(env, task)
turnright = TurnRight(env, task)
turnleft = TurnLeft(env, task)
walkforward = WalkForward(env, task)
standup = StandUp(env, task)

"""

EXPORTS = """
__all__ = [
    "env",
    "task",
    "assert_",
    "putin",
    "putback",
    "find",
    "walk",
    "open",
    "run",
    "close",
    "drink",
    "grab",
    "lookat",
    "walktowards",
    "switchoff",
    "switchon",
    "sit",
    "turnto",
    "pointat",
    "watch",
    "turnright",
    "turnleft",
    "walkforward",
    "standup"
]
"""

EXEC_TASK_FUNCTION: Callable[[str], str] = (
    lambda task_instruction: f"""
def exec_task():
    {task_instruction}()
    return task.finish(env)
"""
)
