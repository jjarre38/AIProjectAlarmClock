"""
Gesture-controlled stopwatch with a jumping-jack alarm.

Normal mode:  show TOGGLE_GESTURE (see config.py) to start/stop the timer.
Alarm:        rings when the stopwatch reaches config.ALARM_SECONDS (if set),
              or when you press 'a' (test).
              1) do config.JACKS_REQUIRED jumping jacks
              2) THEN show TOGGLE_GESTURE to switch the alarm off.
Keys:  q = quit,  r = reset timer + jacks,  a = trigger alarm (test)
"""

import time

import cv2

import config
from gesture_detector import GestureDetector
from gesture_trigger import GestureTrigger
from stopwatch import Stopwatch
from jumping_jack_detect import JumpingJackCounter

JACKS_REQUIRED = getattr(config, "JACKS_REQUIRED", 10)
ALARM_SECONDS = getattr(config, "ALARM_SECONDS", None)  # None = test with 'a' only

# Phases
NORMAL, ALARM_JACKS, ALARM_GESTURE = "normal", "alarm_jacks", "alarm_gesture"

# Skeleton connections between MediaPipe pose landmark indices
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),   # shoulders and arms
    (11, 23), (12, 24), (23, 24),                       # torso
    (23, 25), (25, 27), (24, 26), (26, 28),             # legs
    (27, 29), (29, 31), (28, 30), (30, 32),             # feet
]
KEY_POINTS = {11, 12, 15, 16, 27, 28}  # the landmarks the counter actually uses


def draw_landmarks(frame, landmarks):
    h, w = frame.shape[:2]
    for lm in landmarks:
        cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 255, 0), -1)


def draw_pose(frame, landmarks, state):
    h, w = frame.shape[:2]
    # Green when open, orange when closed, so you can see the state change
    color = (0, 255, 0) if state == "open" else (0, 165, 255)

    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

    for a, b in POSE_CONNECTIONS:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], color, 3)

    # Skip face landmarks (0-10) to keep the view clean
    for i, p in enumerate(pts):
        if i < 11:
            continue
        if i in KEY_POINTS:
            cv2.circle(frame, p, 9, (0, 255, 255), -1)
        else:
            cv2.circle(frame, p, 5, color, -1)


def beep():
    """Best-effort alarm sound without extra dependencies."""
    try:
        import winsound
        winsound.Beep(1000, 150)
    except Exception:
        print("\a", end="", flush=True)


def draw_hud(frame, stopwatch, gesture, score, progress,
             jacks, pose_found, phase, jacks_done):
    h, w = frame.shape[:2]
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

    # Jack counter (top right)
    label = f"Jacks: {jacks}"
    (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.6, 4)
    cv2.putText(frame, label, (w - tw - 20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 255, 0), 4)

    # Alarm banner
    if phase == ALARM_JACKS:
        msg = f"ALARM! Do {JACKS_REQUIRED - jacks_done} more jumping jacks"
        cv2.putText(frame, msg, (20, h - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
    elif phase == ALARM_GESTURE:
        msg = f"Jacks done! Show {config.TOGGLE_GESTURE} to stop the alarm"
        cv2.putText(frame, msg, (20, h - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 3)

    if not pose_found:
        cv2.putText(frame, "No body detected - step back", (20, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)


def main():
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera {config.CAMERA_INDEX}")

    detector = GestureDetector(num_hands=1)
    jack_counter = JumpingJackCounter()
    stopwatch = Stopwatch()
    trigger = GestureTrigger(
        target=config.TOGGLE_GESTURE,
        hold_frames=config.HOLD_FRAMES,
        cooldown_s=config.COOLDOWN_SECONDS,
        min_score=config.MIN_GESTURE_SCORE,
    )
    start = time.monotonic()
    phase = NORMAL
    jack_baseline = 0
    last_beep = 0.0

    def start_alarm():
        nonlocal phase, jack_baseline
        jack_counter.reset()
        jack_baseline = 0
        phase = ALARM_JACKS
        print("[ALARM] ringing - do jumping jacks")

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
            jack_result = jack_counter.update(rgb, timestamp_ms)

            # Full-body skeleton
            if jack_result.landmarks:
                draw_pose(frame, jack_result.landmarks, jack_result.state)

            gesture, score = None, 0.0
            if detections:
                d = detections[0]
                gesture, score = d.gesture, d.score
                draw_landmarks(frame, d.landmarks)

            jacks_done = max(0, jack_result.count - jack_baseline)

            # Alarm trigger from stopwatch time (optional)
            if (phase == NORMAL and ALARM_SECONDS is not None
                    and stopwatch.running and stopwatch.elapsed() >= ALARM_SECONDS):
                stopwatch.toggle()
                start_alarm()

            if phase == NORMAL:
                if trigger.update(gesture, score):
                    stopwatch.toggle()
                    print(f"[{'START' if stopwatch.running else 'STOP'}] {stopwatch.formatted()}")

            elif phase == ALARM_JACKS:
                trigger.update(None, 0.0)  # ignore gestures until jacks are done
                if time.monotonic() - last_beep > 0.7:
                    beep()
                    last_beep = time.monotonic()
                if jacks_done >= JACKS_REQUIRED:
                    phase = ALARM_GESTURE
                    print("[ALARM] jacks done - show the gesture to stop it")

            elif phase == ALARM_GESTURE:
                if time.monotonic() - last_beep > 1.5:  # quieter reminder
                    beep()
                    last_beep = time.monotonic()
                if trigger.update(gesture, score):
                    phase = NORMAL
                    print("[ALARM] stopped")

            draw_hud(frame, stopwatch, gesture, score, trigger.progress,
                     jack_result.count, jack_result.landmarks is not None,
                     phase, jacks_done)
            cv2.imshow("Gesture Timer", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                stopwatch.reset()
                jack_counter.reset()
                jack_baseline = 0
                phase = NORMAL
            if key == ord("a") and phase == NORMAL:
                start_alarm()
    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()