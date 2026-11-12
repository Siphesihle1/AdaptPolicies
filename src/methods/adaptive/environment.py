"""Adaptive Policies' observation and action adapter.

Queries and observation context are the shared adapter's, so AP observes exactly
what CaP observes. Action results additionally carry why an action failed (D3).
"""

from dataclasses import asdict, dataclass

from methods.shared.lmp_environment import ACTION_CLASSES, QUERY_NAMES, LMPEnvironment  # noqa: F401
from methods.shared.lmp_runtime import ATTRIBUTES
from virtual_home.virtualhome_types import ActionResult

# Attribute names AP's generated code may read in addition to CaP's.
AP_ATTRIBUTES = frozenset(ATTRIBUTES | {"message", "recovered"})


@dataclass(frozen=True)
class AdaptiveActionResult(ActionResult):
    message: str | None = None
    # True when the action failed and a recovery achieved its effect.
    recovered: bool = False


class AdaptiveEnvironment(LMPEnvironment):
    def action(self, name, *args):
        result = super().action(name, *args)
        message = None
        if result.status == "failed":
            message = getattr(self.env, "last_action_error", None) or f"{name} failed"
        elif result.status == "skipped":
            message = "The action was skipped by the environment."
        return AdaptiveActionResult(**asdict(result), message=message)
