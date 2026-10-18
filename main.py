"""
Gesture-controlled stopwatch.

Show the TOGGLE_GESTURE (see config.py) to start the timer, show it again to stop.
Keys:  q = quit,  r = reset timer
"""

import time

import cv2

import config
from gesture_detector import GestureDetector
from gesture_trigger import GestureTrigger
from stopwatch import Stopwatch


def draw_landmarks(frame, landmarks):
    h, w = frame.shape[:2]
    for lm in landmarks:
        cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 255, 0), -1)


def draw_hud(frame, stopwatch, gesture, score, progress):
    color = (0, 200, 0) if stopwatch.running else (0, 0, 255)
    state = "RUNNING" if stopwatch.running else "STOPPED"

    cv2.putText(frame, stopwatch.formatted(), (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.8, color, 3)
    cv2.putText(frame, state, (20, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, f"Gesture: {gesture or '-'} ({score:.2f})", (20, 140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, f"Toggle with: {config.TOGGLE_GESTURE}", (20, 170),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    # Hold-progress bar
    cv2.rectangle(frame, (20, 185), (220, 200), (80, 80, 80), 1)
    cv2.rectangle(frame, (20, 185), (20 + int(200 * progress), 200), (0, 255, 255), -1)


def main():
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera {config.CAMERA_INDEX}")

    detector = GestureDetector(num_hands=1)
    stopwatch = Stopwatch()
    trigger = GestureTrigger(
        target=config.TOGGLE_GESTURE,
        hold_frames=config.HOLD_FRAMES,
        cooldown_s=config.COOLDOWN_SECONDS,
        min_score=config.MIN_GESTURE_SCORE,
    )
    start = time.monotonic()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if config.MIRROR_VIEW:
                frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms = int((time.monotonic() - start) * 1000)
            detections = detector.detect(rgb, timestamp_ms)

            gesture, score = None, 0.0
            if detections:
                d = detections[0]
                gesture, score = d.gesture, d.score
                draw_landmarks(frame, d.landmarks)

            if trigger.update(gesture, score):
                stopwatch.toggle()
                print(f"[{'START' if stopwatch.running else 'STOP'}] {stopwatch.formatted()}")

            draw_hud(frame, stopwatch, gesture, score, trigger.progress)
            cv2.imshow("Gesture Timer", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                stopwatch.reset()
    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
