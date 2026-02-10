from typing import Callable


CURRENT_STATE_PROMPT_EXAMPLE = "kitchencounterdrawer, door is OPEN, character, wallpictureframe, clothespile is CLOSED, coffeemaker is OFF, pie, wall, bedroom, microwave is OFF and CLOSED, lightswitch is ON, kitchencabinet is CLOSED, washingsponge, bellpepper, salmon, fridge is CLOSED, wallshelf, tvstand, paper, floor, chips, photoframe, kitchen, whippedcream, candybar, faucet is OFF, tv is OFF, cereal, stovefan, waterglass, cutleryknife, kitchentable, condimentbottle, wineglass, bookshelf, cutleryfork, chocolatesyrup, walllamp, bench, sink, crackers, orchid, condimentshaker, kitchencounter is CLOSED, livingroom, powersocket, coffeepot is CLOSED, creamybuns, ceilinglamp, rug, book is CLOSED, plate, toaster is OFF, clock is OFF, wallphone is OFF, ceiling, fryingpan, box is CLOSED, dishbowl, bananas, breadslice, bathroom, garbagecan is CLOSED, stove is OFF and CLOSED, dishwashingliquid, plate ON kitchencounter, cutleryfork ON kitchentable, bookshelf ON floor, cutleryknife ON kitchentable, bellpepper ON kitchencounter, microwave ON kitchencounterdrawer, chocolatesyrup ON wallshelf, whippedcream ON rug, salmon ON microwave, orchid ON tvstand, wallpictureframe ON wall, bench ON floor, tvstand ON floor, book INSIDE bookshelf, bananas ON dishbowl, toaster ON kitchencounterdrawer, whippedcream ON kitchentable, dishbowl INSIDE bookshelf, fryingpan ON stove, rug ON kitchentable, coffeepot INSIDE coffeemaker, waterglass ON rug, dishwashingliquid ON kitchencounter, wallshelf ON wall, washingsponge ON kitchencounter, clothespile INSIDE bookshelf, bananas INSIDE bookshelf, box ON bookshelf, plate ON kitchentable, waterglass ON kitchentable, creamybuns ON wallshelf, breadslice INSIDE toaster, coffeemaker ON kitchencounterdrawer, chips ON wallshelf, book ON kitchentable, dishbowl ON bookshelf, pie ON kitchentable, wineglass ON tvstand, box ON tvstand, coffeepot ON kitchencounter, bellpepper ON kitchencounterdrawer, condimentshaker INSIDE bookshelf, coffeemaker ON kitchencounter, toaster ON kitchencounter, box INSIDE bookshelf, crackers ON wallshelf, character HOLDS_RH book, faucet ON kitchencounter, book ON rug, cereal ON wallshelf, plate INSIDE microwave, candybar ON wallshelf, condimentbottle INSIDE bookshelf, tv ON tvstand, microwave ON kitchencounter, paper INSIDE bookshelf, kitchencounterdrawer ON kitchencounter, fridge ON floor, photoframe ON tvstand, wallpictureframe ON wallpictureframe, bench ON rug, pie ON rug, kitchencounterdrawer ON kitchencounterdrawer, dishbowl ON kitchencounter.\n\nassert('close' to 'mug' )\nFalse\nassert('close' to 'microwave' )\nTrue\nassert('book' is 'closed' )\nTrue\nassert('lightswitch' is 'OFF')\nFalse\nassert('book' in 'bookshelf')\nTrue\nassert('book' in 'hands')\nTrue\nassert('cereal' on 'bookshelf')\nFalse"

ASSERT_PROMPT_PREAMBLE = """You are a character in a virtual home simulator.

Task: Evaluate assert statements using the given state (what you see i.e. "You see: ...")

<rules>
- Return 'True' or 'False' only
- State facts are literal and complete.
- The answer token MUST be emitted immediately.
- Do not generate analysis before the answer.
- Do not explain your answer or you reasoning behind it, just output the answer token (either True or False).
</rules>

<assert-rules>
- assert('close' to A) is True if A is close to the character, in other words it can be seen by the character (you)
- assert(A on B) is True if "A ON B" exists in state
- assert(A in B) is True if "A INSIDE B" exists in state
- assert(A is 'closed' | 'open' | 'on' | 'off' | ...) checks object state with correposponding values CLOSED, OPEN, ON, OFF, ...
- "hands" means the character is holding the object (HOLDS_RH or HOLDS_LH)
</assert-rules>

<output-format>
- Output exactly ONE token.
- The token MUST be either:
  True
  False
- Do not include punctuation, explanation, whitespace, or newlines.
- Any other output is invalid.
</output-format>

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

TASK_INIT: Callable[[str, str, int], str] = (
    lambda task_instruction, thread_id, max_steps: f"""
task = VHTask("{task_instruction}", "{thread_id}", SUBTASKS, max_steps={max_steps})
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

TASK_PROMPT_ACTION_IMPORTS = "from actions import turnright, turnleft, walkforward, walk <obj>, run <obj>, grab <obj>, switchon <obj>, switchoff <obj>, open <obj>, close <obj>, lookat <obj>, sit <obj>, standup, find <obj>, turnto <obj>, drink <obj>, pointat <obj>, watch <obj>, putin <obj> <obj>, putback <obj> <obj>"

DEFAULT_EXAMPLES = [
    "put_the_wine_glass_in_the_kitchen_cabinet",
    "throw_away_the_lime",
    "refrigerate_the_salmon",
    "bring_me_some_fruit",
    "wash_clothes",
    "put_apple_in_fridge",
]

TASK_FUNCTION_PROMPT_PREAMBLE = """You are an action-planning code generator for a virtual home simulator.

Task: You are given a function header that describes a virtual home household task. You must generate the complete function body that accomplishes the task (with the function header included) in a python-like syntax.

<rules>
- Do NOT generate analysis before the function code.
- Infer all required subtasks yourself.
- Each subtask must be documented with a numbered comment.
- Subtask numbering must start at 0 and increase by 1.
- Each subtask comment must describe the intent of the following actions.
- Follow the exact style, structure, and conventions shown in the examples.
- Use ONLY the provided actions and objects (actions provided via imports at the top and availables objects as a list).
- Do NOT invent new actions, objects, or syntax.
- Do NOT skip steps, merge steps, or assume shortcuts.
- You MUST find an object first before interacting with it.
- Before finding or interacting with an object, you should first walk to the room that most likely contains the object.
- Not all actions can be applied to all objects.
- You must only choose actions that make sense for the object.
- If an action does not logically apply to an object, DO NOT use it.
- Actions that do not make sense for an object are strictly forbidden.
- When in doubt, prefer `find`, `walk`, or `lookat` over applying an invalid action.
- Some objects (movable objects) must be in the agent's hands before they can be used or interacted with. For these objects, the agent must grab the object before performing any other action with it.
- Do NOT attempt to grab fixed objects or containers.
- Never interact with a handheld object unless it is first in the agent's hands.
- You must include all actions required to reach a sensible final state.
- You must not end a task while objects are in an intermediate or transient state.
- Always include the 'Done' step to indicate the end of the task as demontrated in the example.
- For actions that require the agent to be facing an object, ensure the agent is looking at the object before interacting with the it.
- Each action should be referenced exactly as it is shown in the imports without any additional characters or mofifications.
</rules>

<output-format>
- Output ONLY the completed function.
- The function MUST include the header and body.
- Do NOT include markdown, backticks, or explanations.
- Do NOT include explanations, markdown, or text outside the function.
- Stop immediately after the function ends.
- Be consistent with indentation as shown in the example.
- The output is NOT natural language.
- The output is a strict action script.
- Sentence punctuation (., !) is never allowed anywhere in the output.
</output-format>

<assert-syntax-rules>
- The `assert` statements in this code are part of a custom domain-specific language. They do NOT follow standard Python syntax and must be reproduced exactly as shown.
- The `assert` statements check whether the condition is true in the current state of the environment. If true, nothing happends and the agent continues with the next action. If false, the agent must perform the action(s) specified in the `else:` lines in order, and then continues with the next action.
- Valid assert forms:
```
1. Proximity check:
	assert('close' to OBJECT)
		else: ACTION(OBJECT)

2. State check:
	assert(OBJECT is STATE)
		else: ACTION(OBJECT)

3. Possession check:
	assert(OBJECT in 'hands')
		else: grab(OBJECT)

4. Location check:
    assert(OBJECT on LOCATION)
        else: ACTION(OBJECT)
    
    OR

    assert(OBJECT in LOCATION)
        else: ACTION(OBJECT)
```
- The `else:` line(s) must be on the next line and indented once with the action function call on the same line.
- An `assert` may contain one or more `else:` lines.
- Do NOT rewrite, optimize, or correct assert syntax.
- Do NOT replace asserts with if-statements.
- Always follow the patterns demonstrated in the examples.
</assert-syntax-rules>
"""
