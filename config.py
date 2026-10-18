"""Central place for tunable settings."""

from pathlib import Path

# --- Model ---
MODEL_PATH = Path(__file__).parent / "models" / "gesture_recognizer.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float16/1/gesture_recognizer.task"
)

# --- Camera ---
CAMERA_INDEX = 0
MIRROR_VIEW = True  # flip horizontally so it feels like a mirror

# --- Gesture -> action ---
# Built-in gesture names: "None", "Closed_Fist", "Open_Palm", "Pointing_Up",
# "Thumb_Down", "Thumb_Up", "Victory", "ILoveYou"
TOGGLE_GESTURE = "Victory"

MIN_GESTURE_SCORE = 0.6   # confidence threshold for accepting a gesture
HOLD_FRAMES = 8           # gesture must be seen this many consecutive frames to trigger
COOLDOWN_SECONDS = 1.0    # minimum time between two toggles
