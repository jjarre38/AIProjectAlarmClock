"""Thin wrapper around MediaPipe's Pose Landmarker task that counts jumping jacks."""

import urllib.request
from dataclasses import dataclass
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

# Defaults; swap these for config.MODEL_PATH / config.MODEL_URL if you keep
# everything in a shared config module like gesture_detector does.
DEFAULT_MODEL_PATH = Path("models/pose_landmarker_lite.task")
DEFAULT_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

# Pose landmark indices
L_SHOULDER, R_SHOULDER = 11, 12
L_WRIST, R_WRIST = 15, 16
L_ANKLE, R_ANKLE = 27, 28


@dataclass
class JackResult:
    pose: str | None        # "open", "closed", or None while in transition
    state: str              # last stable pose: "open" or "closed"
    count: int              # completed jumping jacks so far
    landmarks: list | None  # 33 normalized landmarks, or None if no person found


def ensure_model(path: Path = DEFAULT_MODEL_PATH, url: str = DEFAULT_MODEL_URL):
    """Download the pose model on first run."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading model to {path} ...")
        urllib.request.urlretrieve(url, path)


class JumpingJackCounter:
    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        model_url: str = DEFAULT_MODEL_URL,
        legs_apart_ratio: float = 1.5,
        legs_together_ratio: float = 1.1,
    ):
        ensure_model(model_path, model_url)
        options = vision.PoseLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._apart_ratio = legs_apart_ratio
        self._together_ratio = legs_together_ratio
        self.state = "closed"
        self.count = 0

    def reset(self):
        """Zero the counter and return to the starting state."""
        self.state = "closed"
        self.count = 0

    def update(self, rgb_frame, timestamp_ms: int) -> JackResult:
        """Process one RGB frame. Timestamps must increase monotonically."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.pose_landmarks:
            return JackResult(None, self.state, self.count, None)

        landmarks = result.pose_landmarks[0]
        pose = self._classify(landmarks)

        if pose == "open" and self.state == "closed":
            self.state = "open"
        elif pose == "closed" and self.state == "open":
            self.state = "closed"
            self.count += 1  # full cycle completed

        return JackResult(pose, self.state, self.count, landmarks)

    def _classify(self, lm) -> str | None:
        # y increases downward in image coordinates
        shoulder_y = (lm[L_SHOULDER].y + lm[R_SHOULDER].y) / 2
        shoulder_w = abs(lm[L_SHOULDER].x - lm[R_SHOULDER].x)
        ankle_w = abs(lm[L_ANKLE].x - lm[R_ANKLE].x)

        arms_up = lm[L_WRIST].y < shoulder_y and lm[R_WRIST].y < shoulder_y
        arms_down = lm[L_WRIST].y > shoulder_y and lm[R_WRIST].y > shoulder_y
        legs_apart = ankle_w > self._apart_ratio * shoulder_w
        legs_together = ankle_w < self._together_ratio * shoulder_w

        if arms_up and legs_apart:
            return "open"
        if arms_down and legs_together:
            return "closed"
        return None  # in transition, keep previous state

    def close(self):
        self._landmarker.close()


if __name__ == "__main__":
    import time

    import cv2

    counter = JumpingJackCounter()
    cap = cv2.VideoCapture(0)
    start = time.monotonic()
    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Wall-clock timestamps are always monotonic for a live webcam
            # (CAP_PROP_POS_MSEC can be 0 or repeat on some cameras).
            ts = int((time.monotonic() - start) * 1000)
            res = counter.update(rgb, ts)

            cv2.putText(frame, f"Jumping jacks: {res.count}", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
            cv2.imshow("jacks", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        counter.close()
        cap.release()
        cv2.destroyAllWindows()