"""Backend for the React alarm GUI.

Put this file next to alarm.py and run it from that folder:

    uvicorn server:app --port 8000

The server owns the alarm: it keeps the target time, decides when the alarm
starts ringing, and decides when it stops. Once it is ringing, turning it off
takes two steps, in order:

  1. do config.JACKS_REQUIRED jumping jacks (full body in front of the camera)
  2. THEN show config.ALARM_OFF_GESTURE to the camera

The gesture is ignored until the jacks are done. The React app only displays
that state, lets you set the alarm, and plays the sound in the browser.
"""
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from alarm import next_occurrence  # reuse the logic from alarm.py
from gesture_detector import GestureDetector
from gesture_trigger import GestureTrigger
from jumping_jack_detect import JumpingJackCounter, ensure_model

JACKS_REQUIRED = getattr(config, "JACKS_REQUIRED", 3)

PHASE_JACKS, PHASE_GESTURE = "jacks", "gesture"

lock = threading.Lock()
stop_event = threading.Event()
state = {
    "target": None,
    "ringing": False,
    "sound": "beep",
    "phase": PHASE_JACKS,   # "jacks" first, then "gesture"
    "jacks": 0,             # jacks counted since the alarm started
    "pose_found": True,     # False when no body is visible
    "gesture": None,        # what the camera currently sees while ringing
    "progress": 0.0,        # 0..1 toward holding the off gesture long enough
    "camera_error": None,   # set if the camera/model can't run
    "frame": None,          # latest annotated JPEG from the camera
}

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


def draw_pose(frame, landmarks, jack_state):
    h, w = frame.shape[:2]
    # Green when open, orange when closed, so you can see the state change
    color = (0, 255, 0) if jack_state == "open" else (0, 165, 255)
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


def watch_for_gesture(stop_event):
    """Camera loop: jumping jacks first, then the off gesture.

    Sets stop_event once the gesture has been held after the jacks are done.
    """
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera {config.CAMERA_INDEX}")

    detector = GestureDetector(num_hands=1)
    jack_counter = JumpingJackCounter()
    trigger = GestureTrigger(
        target=config.ALARM_OFF_GESTURE,
        hold_frames=config.ALARM_HOLD_FRAMES,
        cooldown_s=0,
        min_score=config.MIN_GESTURE_SCORE,
    )
    start = time.monotonic()
    phase = PHASE_JACKS

    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Lost the camera feed")
            if config.MIRROR_VIEW:
                frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms = int((time.monotonic() - start) * 1000)
            detections = detector.detect(rgb, timestamp_ms)
            jack_result = jack_counter.update(rgb, timestamp_ms)

            # Full-body skeleton, always
            if jack_result.landmarks:
                draw_pose(frame, jack_result.landmarks, jack_result.state)

            gesture, score = None, 0.0
            if detections:
                d = detections[0]
                gesture, score = d.gesture, d.score
                if phase == PHASE_GESTURE:
                    draw_landmarks(frame, d.landmarks)

            fired = False
            if phase == PHASE_JACKS:
                trigger.update(None, 0.0)  # gesture is ignored until jacks are done
                if jack_result.count >= JACKS_REQUIRED:
                    phase = PHASE_GESTURE
            else:
                fired = trigger.update(gesture, score)

            _, jpeg = cv2.imencode(".jpg", frame)
            with lock:
                state["phase"] = phase
                state["jacks"] = min(jack_result.count, JACKS_REQUIRED)
                state["pose_found"] = jack_result.landmarks is not None
                state["gesture"] = gesture if phase == PHASE_GESTURE else None
                if phase == PHASE_GESTURE:
                    state["progress"] = 1.0 if fired else trigger.progress
                else:
                    state["progress"] = 0.0
                state["frame"] = jpeg.tobytes()

            if fired:
                stop_event.set()
    finally:
        detector.close()
        jack_counter.close()
        cap.release()


def detect_turn_off(stop_event):
    """Decides when the alarm is turned off.

    Runs in its own thread the moment the alarm starts ringing. If the camera
    or model can't run, the error is reported so the app can fall back to a
    button instead of ringing forever.
    """
    try:
        watch_for_gesture(stop_event)
    except Exception as e:
        print(f"Gesture detection failed: {e}")
        with lock:
            state["camera_error"] = str(e)


class AlarmIn(BaseModel):
    time: str  # "HH:MM", 24-hour
    sound: str = "beep"


def snapshot():
    target = state["target"]
    return {
        "target": target.isoformat() if target else None,
        "ringing": state["ringing"],
        "sound": state["sound"],
        "required_gesture": config.ALARM_OFF_GESTURE,
        "phase": state["phase"],
        "jacks": state["jacks"],
        "jacks_required": JACKS_REQUIRED,
        "pose_found": state["pose_found"],
        "gesture": state["gesture"],
        "progress": state["progress"],
        "camera_error": state["camera_error"],
    }


def finish_alarm():
    """Clear the alarm. Call with the lock held."""
    state["ringing"] = False
    state["target"] = None
    state["frame"] = None
    stop_event.set()


def scheduler():
    """Checks the clock a few times a second and starts/ends ringing."""
    while True:
        with lock:
            if state["ringing"]:
                if stop_event.is_set():  # detect_turn_off saw the gesture
                    finish_alarm()
            elif state["target"] and datetime.now() >= state["target"]:
                state.update(
                    ringing=True,
                    phase=PHASE_JACKS,
                    jacks=0,
                    pose_found=True,
                    gesture=None,
                    progress=0.0,
                    camera_error=None,
                )
                stop_event.clear()
                threading.Thread(
                    target=detect_turn_off, args=(stop_event,), daemon=True
                ).start()
        time.sleep(0.2)


@asynccontextmanager
async def lifespan(app):
    # Download the pose model now, not at the moment the alarm rings.
    try:
        ensure_model()
    except Exception as e:
        print(f"Could not fetch the pose model yet: {e}")
    threading.Thread(target=scheduler, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/status")
def get_status():
    with lock:
        return snapshot()


@app.post("/api/alarm")
def set_alarm(body: AlarmIn):
    try:
        alarm_time = datetime.strptime(body.time, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Time must look like HH:MM")
    with lock:
        if state["ringing"]:
            raise HTTPException(status_code=409, detail="The alarm is ringing right now")
        state["target"] = next_occurrence(alarm_time)
        state["sound"] = body.sound
        return snapshot()


@app.delete("/api/alarm")
def cancel_alarm():
    with lock:
        if state["ringing"]:
            raise HTTPException(
                status_code=409,
                detail="Do the jumping jacks, then show the gesture, to turn off a ringing alarm",
            )
        finish_alarm()
        return snapshot()


@app.post("/api/turn-off")
def turn_off():
    """Manual fallback, only allowed when the camera can't be used."""
    with lock:
        if state["ringing"] and not state["camera_error"]:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Do {JACKS_REQUIRED} jumping jacks, then show "
                    f"{config.ALARM_OFF_GESTURE} to the camera to turn it off"
                ),
            )
        finish_alarm()
        return snapshot()


@app.get("/api/camera")
def camera_feed():
    """Live MJPEG view of what the camera sees (with skeleton), while ringing."""

    def frames():
        last = None
        while True:
            with lock:
                ringing, frame = state["ringing"], state["frame"]
            if not ringing:
                return
            if frame is not None and frame is not last:
                last = frame
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(0.03)

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )