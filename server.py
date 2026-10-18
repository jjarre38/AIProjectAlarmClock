"""Backend for the React alarm GUI.

Put this file next to alarm.py and run it from that folder:

    uvicorn server:app --port 8000

The server owns the alarm: it keeps the target time, decides when the alarm
starts ringing, and decides when it stops. Once it is ringing, the only way
to stop it is to show config.ALARM_OFF_GESTURE to the camera. The React app
only displays that state, lets you set it, and plays the sound in the browser.
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

lock = threading.Lock()
stop_event = threading.Event()
state = {
    "target": None,
    "ringing": False,
    "sound": "beep",
    "gesture": None,        # what the camera currently sees while ringing
    "progress": 0.0,        # 0..1 toward holding the off gesture long enough
    "camera_error": None,   # set if the camera/model can't run
    "frame": None,          # latest annotated JPEG from the camera
}


def draw_landmarks(frame, landmarks):
    h, w = frame.shape[:2]
    for lm in landmarks:
        cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 255, 0), -1)


def watch_for_gesture(stop_event):
    """Camera loop: sets stop_event once the off gesture has been held."""
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera {config.CAMERA_INDEX}")

    detector = GestureDetector(num_hands=1)
    trigger = GestureTrigger(
        target=config.ALARM_OFF_GESTURE,
        hold_frames=config.ALARM_HOLD_FRAMES,
        cooldown_s=0,
        min_score=config.MIN_GESTURE_SCORE,
    )
    start = time.monotonic()

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

            gesture, score = None, 0.0
            if detections:
                d = detections[0]
                gesture, score = d.gesture, d.score
                draw_landmarks(frame, d.landmarks)

            fired = trigger.update(gesture, score)
            _, jpeg = cv2.imencode(".jpg", frame)
            with lock:
                state["gesture"] = gesture
                state["progress"] = 1.0 if fired else trigger.progress
                state["frame"] = jpeg.tobytes()

            if fired:
                stop_event.set()
    finally:
        detector.close()
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
                state.update(ringing=True, gesture=None, progress=0.0, camera_error=None)
                stop_event.clear()
                threading.Thread(
                    target=detect_turn_off, args=(stop_event,), daemon=True
                ).start()
        time.sleep(0.2)


@asynccontextmanager
async def lifespan(app):
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
                status_code=409, detail="Show the gesture to turn off a ringing alarm"
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
                detail=f"Show {config.ALARM_OFF_GESTURE} to the camera to turn it off",
            )
        finish_alarm()
        return snapshot()


@app.get("/api/camera")
def camera_feed():
    """Live MJPEG view of what the gesture model sees, while ringing."""

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
