import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

options = vision.PoseLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_path="pose_landmarker_lite.task"),
    running_mode=vision.RunningMode.VIDEO,
)
landmarker = vision.PoseLandmarker.create_from_options(options)

state = "closed"
count = 0

def classify(lm):
    # y increases downward in image coordinates
    l_sh, r_sh = lm[11], lm[12]
    l_wr, r_wr = lm[15], lm[16]
    l_an, r_an = lm[27], lm[28]

    shoulder_y = (l_sh.y + r_sh.y) / 2
    shoulder_w = abs(l_sh.x - r_sh.x)
    ankle_w = abs(l_an.x - r_an.x)

    arms_up = l_wr.y < shoulder_y and r_wr.y < shoulder_y
    arms_down = l_wr.y > shoulder_y and r_wr.y > shoulder_y
    legs_apart = ankle_w > 1.5 * shoulder_w
    legs_together = ankle_w < 1.1 * shoulder_w

    if arms_up and legs_apart:
        return "open"
    if arms_down and legs_together:
        return "closed"
    return None  # in transition, keep previous state

cap = cv2.VideoCapture(0)
while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect_for_video(mp_img, int(cap.get(cv2.CAP_PROP_POS_MSEC)))

    if result.pose_landmarks:
        s = classify(result.pose_landmarks[0])
        if s == "open" and state == "closed":
            state = "open"
        elif s == "closed" and state == "open":
            state = "closed"
            count += 1  # full cycle completed

    cv2.putText(frame, f"Jumping jacks: {count}", (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    cv2.imshow("jacks", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break