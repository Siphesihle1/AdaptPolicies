"""Adaptive Policies settings: the shared runtime limits plus checkpoint and recovery settings."""

from dataclasses import dataclass, fields

from methods.shared.lmp_runtime import Limits, time_is_finite

PURPOSES = {"policy": "ap_policy", "function": "ap_function", "objects": "ap_objects",
            "question": "ap_question", "recover": "ap_recover", "replan": "ap_replan"}
# Which checkpoint triggers each placement condition enables. Exceptions raised by
# generated code are recovered in every condition.
PLACEMENTS = {
    "both": {"explicit": True, "implicit": True},
    "explicit": {"explicit": True, "implicit": False},
    "implicit": {"explicit": False, "implicit": True},
}


@dataclass(frozen=True)
class AdaptiveLimits(Limits):
    # Recoveries need model calls, so AP's request budget is larger than CaP's 32.
    max_model_requests: int = 64
    placement: str = "both"
    # Local recoveries at one failure site, and regenerations of one helper,
    # before escalating to the next recovery scope.
    max_recoveries_per_checkpoint: int = 2

    def __post_init__(self):
        if self.placement not in PLACEMENTS:
            raise ValueError(f"placement must be one of {sorted(PLACEMENTS)}")
        for field in fields(self):
            if field.name == "placement":
                continue
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{field.name} must be positive")
            if field.name != "task_seconds" and type(value) is not int:
                raise ValueError(f"{field.name} must be an integer")
        if not time_is_finite(self.task_seconds):
            raise ValueError("task_seconds must be finite")

    @property
    def explicit(self):
        return PLACEMENTS[self.placement]["explicit"]

    @property
    def implicit(self):
        return PLACEMENTS[self.placement]["implicit"]
