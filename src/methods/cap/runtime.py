"""CaP policy runtime: the shared LMP runtime with CaP's session and trace labels."""

from methods.shared.lmp_runtime import (ATTRIBUTES, BUILTINS, DENIED_NAMES, Budget, Limits,  # noqa: F401
                                        serialize, time_is_finite, validate)
from methods.shared.lmp_runtime import PolicyRuntime as LMPPolicyRuntime
from .lmp import Session


class PolicyRuntime(LMPPolicyRuntime):
    session_class = Session
    observation_label = "CaP observation"
    action_span, query_span = "cap_action", "cap_query"
