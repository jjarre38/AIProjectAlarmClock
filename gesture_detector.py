"""Thin wrapper around MediaPipe's Gesture Recognizer task."""

import urllib.request
from dataclasses import dataclass

import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

import config


@dataclass
class Detection:
    gesture: str            # e.g. "Victory", or "None"
    score: float
    landmarks: list         # 21 normalized landmarks (x, y in [0, 1])


def ensure_model():
    """Download the gesture model on first run."""
    if not config.MODEL_PATH.exists():
        config.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading model to {config.MODEL_PATH} ...")
        urllib.request.urlretrieve(config.MODEL_URL, config.MODEL_PATH)


class GestureDetector:
    def __init__(self, num_hands: int = 1):
        ensure_model()
        options = vision.GestureRecognizerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(config.MODEL_PATH)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)

    def detect(self, rgb_frame, timestamp_ms: int) -> list[Detection]:
        """Run recognition on one RGB frame. Timestamps must increase monotonically."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._recognizer.recognize_for_video(mp_image, timestamp_ms)

        detections = []
        for gestures, landmarks in zip(result.gestures, result.hand_landmarks):
            top = gestures[0]  # highest-scoring gesture for this hand
            detections.append(Detection(top.category_name, top.score, landmarks))
        return detections

    def close(self):
        self._recognizer.close()
