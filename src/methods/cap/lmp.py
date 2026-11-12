"""CaP language model programs: the shared session with CaP's purposes and prompts."""

from methods.shared.lmp_session import LMP  # noqa: F401
from methods.shared.lmp_session import Session as LMPSession
from .prompt import build_prompt

PURPOSES = {"policy": "cap_policy", "function": "cap_function",
            "objects": "cap_objects", "question": "cap_question"}


class Session(LMPSession):
    purposes = PURPOSES
    build_prompt = staticmethod(build_prompt)
