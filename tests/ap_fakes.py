"""Deterministic collaborators for Adaptive Policies tests; no model or simulator is contacted."""

import re
from xml.sax.saxutils import unescape

from cap_fakes import FakeEnvironment


class SequenceProvider:
    """Scripted model: each purpose maps to one response or a list used in order.

    The last response of a list repeats once the list is used up. A dict maps a
    substring of the request's first line to the response for that request.
    """

    def __init__(self, responses):
        self.responses = responses
        self.calls = {}

    def __call__(self, prompt, purpose):
        response = self.responses[purpose]
        if isinstance(response, dict):
            match = re.search(r"<(task|request)>\n(.*?)\n</\1>", prompt, re.S)
            request = unescape(match[2]).splitlines()[0]
            response = next(value for key, value in response.items() if key in request)
        if isinstance(response, list):
            index = self.calls.get(purpose, 0)
            self.calls[purpose] = index + 1
            response = response[min(index, len(response) - 1)]
        return response


class FlakyEnvironment(FakeEnvironment):
    """Fails the named actions a given number of times before they succeed."""

    failures = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.remaining = dict(self.failures)

    def execute(self, script):
        action = re.search(r"\[(\w+)\]", script)[1]
        if self.remaining.get(action, 0) > 0:
            self.remaining[action] -= 1
            self.calls.append(script)
            self.last_action_error = f"{action} is not possible yet"
            return False
        return super().execute(script)
