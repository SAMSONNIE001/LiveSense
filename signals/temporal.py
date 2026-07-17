"""Temporal confirmation for stable live observations."""

from __future__ import annotations


class StableObservation:
    """Confirm boolean state changes only after they remain stable for a duration."""

    def __init__(self, activate_seconds: float, clear_seconds: float) -> None:
        self.activate_seconds = activate_seconds
        self.clear_seconds = clear_seconds
        self.active = False
        self._candidate = False
        self._candidate_since: float | None = None

    def update(self, observed: bool, timestamp: float) -> bool:
        if observed != self._candidate:
            self._candidate = observed
            self._candidate_since = timestamp
        if observed == self.active:
            self._candidate_since = timestamp
            return self.active
        if self._candidate_since is None:
            self._candidate_since = timestamp
            return self.active
        required = self.activate_seconds if observed else self.clear_seconds
        if timestamp - self._candidate_since >= required:
            self.active = observed
            self._candidate_since = timestamp
        return self.active

    def reset(self) -> None:
        self.active = False
        self._candidate = False
        self._candidate_since = None
