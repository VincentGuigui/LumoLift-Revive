"""Persistent local continuity for raw Lumo step counters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
import os
from pathlib import Path


@dataclass
class CounterState:
    day: str
    steps_raw: int = 0
    steps_displayed: int = 0
    stepsh_raw: int = 0
    stepsh_displayed: int = 0


class CounterStore:
    """Keep daily counters continuous across sensor/app counter restarts.

    The sensor provides raw counters. If a same-day raw value decreases, the
    store treats that as a restarted baseline and carries the previous displayed
    total forward. State resets at the next local calendar day.
    """

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            app_data = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            path = app_data / "LumoLiftRevive" / "counters.json"
        self.path = path
        self._state = self._load()

    def snapshot(self) -> CounterState:
        self._ensure_day()
        return CounterState(**asdict(self._state))

    def update_steps(self, raw_value: int, day: str | None = None) -> CounterState:
        self._ensure_day(day)
        self._state.steps_displayed += self._delta(raw_value, self._state.steps_raw)
        self._state.steps_raw = raw_value
        self._save()
        return CounterState(**asdict(self._state))

    def update_stepsh(self, raw_value: int, day: str | None = None) -> CounterState:
        self._ensure_day(day)
        self._state.stepsh_displayed += self._delta(raw_value, self._state.stepsh_raw)
        self._state.stepsh_raw = raw_value
        self._save()
        return CounterState(**asdict(self._state))

    @staticmethod
    def _delta(raw_value: int, previous_raw: int) -> int:
        raw_value = max(0, int(raw_value))
        previous_raw = max(0, int(previous_raw))
        if raw_value >= previous_raw:
            return raw_value - previous_raw
        # A new raw baseline starts at zero; preserve the displayed total.
        return raw_value

    def _ensure_day(self, day: str | None = None) -> None:
        current_day = day or date.today().isoformat()
        if self._state.day != current_day:
            self._state = CounterState(day=current_day)
            self._save()

    def _load(self) -> CounterState:
        current_day = date.today().isoformat()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return CounterState(
                day=str(data.get("day", current_day)),
                steps_raw=max(0, int(data.get("steps_raw", 0))),
                steps_displayed=max(0, int(data.get("steps_displayed", 0))),
                stepsh_raw=max(0, int(data.get("stepsh_raw", 0))),
                stepsh_displayed=max(0, int(data.get("stepsh_displayed", 0))),
            )
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return CounterState(day=current_day)

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(self._state)), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            # Counters remain usable in memory if local persistence is unavailable.
            pass
