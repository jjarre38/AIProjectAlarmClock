import time

import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles

CAMERA_INDEX = 0          # change if you have multiple cameras
DELAY_SECONDS = 3         # countdown before the picture is taken
MODEL_PATH = "pose_landmarker_heavy.task"
SAVE_PATH = "annotated.jpg"


def draw_landmarks_on_image(rgb_image, detection_result):
    pose_landmarks_list = detection_result.pose_landmarks
    annotated_image = np.copy(rgb_image)

    pose_landmark_style = drawing_styles.get_default_pose_landmarks_style()
    pose_connection_style = drawing_utils.DrawingSpec(color=(0, 255, 0), thickness=2)

    for pose_landmarks in pose_landmarks_list:
        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=pose_landmarks,
            connections=vision.PoseLandmarksConnections.POSE_LANDMARKS,
            landmark_drawing_spec=pose_landmark_style,
            connection_drawing_spec=pose_connection_style)

    return annotated_image


def capture_after_delay(delay=DELAY_SECONDS, camera_index=CAMERA_INDEX):
    """Show a live preview with a countdown, then return one BGR frame."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera {camera_index}")

    frame = None
    start = time.time()
    try:
        # Keep reading frames during the wait so the camera can adjust exposure
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Failed to read a frame from the camera")

            remaining = delay - (time.time() - start)
            if remaining <= 0:
                break

            preview = frame.copy()
            cv2.putText(preview, str(int(np.ceil(remaining))), (30, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 255, 255), 5)
            cv2.imshow("Pose", preview)
            cv2.waitKey(1)
    finally:
        cap.release()

    return frame  # the last frame read, taken right as the countdown ended


# --- Set up the detector ---
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.PoseLandmarkerOptions(base_options=base_options)
detector = vision.PoseLandmarker.create_from_options(options)

# --- Wait 3 seconds, then take the picture ---
bgr_frame = capture_after_delay()
rgb_frame = np.ascontiguousarray(cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB))

# --- Analyze it ---
image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
detection_result = detector.detect(image)

if not detection_result.pose_landmarks:
    print("No pose detected in the captured image.")

annotated = draw_landmarks_on_image(image.numpy_view(), detection_result)
annotated_bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)

cv2.imwrite(SAVE_PATH, annotated_bgr)
print(f"Saved result to {SAVE_PATH}")

cv2.imshow("Pose", annotated_bgr)
cv2.waitKey(0)
cv2.destroyAllWindows()