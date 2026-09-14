"""UI-independent step counters and local goal calculations."""

from __future__ import annotations


MIN_STEPS_GOAL = 100
DEFAULT_STEPS_GOAL = 10_000


def validate_steps_goal(goal: int) -> int:
    goal = int(goal)
    if goal < MIN_STEPS_GOAL:
        raise ValueError(f"Steps goal must be at least {MIN_STEPS_GOAL}")
    return goal


def progress_percent(value: int, goal: int) -> int:
    """Return a clamped 0–100 progress value for a counter and local goal."""

    goal = validate_steps_goal(goal)
    return max(0, min(100, round(100 * max(0, int(value)) / goal)))
