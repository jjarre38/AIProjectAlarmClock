"""Turns a noisy per-frame gesture stream into clean one-shot trigger events."""

import time


class GestureTrigger:
    """
    Fires once when `target` has been held for `hold_frames` consecutive frames.
    It won't fire again until the gesture is released (and the cooldown has passed),
    so holding the gesture doesn't flip the timer on and off over and over.
    """

    def __init__(self, target: str, hold_frames: int, cooldown_s: float, min_score: float):
        self.target = target
        self.hold_frames = hold_frames
        self.cooldown_s = cooldown_s
        self.min_score = min_score

        self._streak = 0
        self._armed = True
        self._last_fire = 0.0

    def update(self, gesture: str | None, score: float = 0.0) -> bool:
        """Feed the current frame's gesture. Returns True on the frame the trigger fires."""
        seen = gesture == self.target and score >= self.min_score

        if not seen:
            self._streak = 0
            self._armed = True  # gesture released, so allow the next trigger
            return False

        self._streak += 1
        now = time.monotonic()
        if (
            self._armed
            and self._streak >= self.hold_frames
            and now - self._last_fire >= self.cooldown_s
        ):
            self._armed = False
            self._last_fire = now
            return True
        return False

    @property
    def progress(self) -> float:
        """0..1 progress toward firing, useful for UI feedback."""
        if not self._armed:
            return 0.0
        return min(self._streak / self.hold_frames, 1.0)
