"""UI-independent interpretation of Lumo live posture events."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PostureThresholds:
    """Local display thresholds; these do not configure the physical sensor."""

    forward_below_degrees: float = 85.0
    backward_above_degrees: float = 95.0

    def __post_init__(self) -> None:
        if self.forward_below_degrees >= self.backward_above_degrees:
            raise ValueError("forward threshold must be below backward threshold")


def classify_posture(
    activity: str | None,
    angle_degrees: float | None,
    thresholds: PostureThresholds = PostureThresholds(),
) -> str:
    """Classify a REC event using the original app's documented approach."""

    if activity in (None, "inactive", "not_worn") or angle_degrees is None:
        return "not worn"
    if angle_degrees < thresholds.forward_below_degrees:
        return "forward"
    if angle_degrees > thresholds.backward_above_degrees:
        return "back"
    return "good"
