# AIProjectAlarmClock

A gesture- and exercise-controlled alarm clock. The Python backend (FastAPI) owns
the alarm and watches the webcam. Once the alarm rings, turning it off takes
**two steps, in order**:

1. **Do jumping jacks** in front of the camera (3 by default).
2. **Then show the off gesture** (`ALARM_OFF_GESTURE` in `config.py`, default
   `Victory` ✌️) and hold it until the progress bar fills.

The gesture is ignored until the jumping jacks are done. The React frontend
displays the alarm state and a live camera view with your skeleton drawn on it,
lets you set the time and pick a sound, and plays the sound in the browser.

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- A webcam, with enough room to step back so your **whole body** (head to
  ankles) is in frame for the jumping jacks

## Running the backend

From the project root:

```bash
# Create and activate a virtual environment (first time only)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install fastapi uvicorn

# Start the server on port 8000
uvicorn server:app --port 8000
```

Two MediaPipe models are used, and both are downloaded to `models/`
automatically if they aren't already there:

- `gesture_recognizer.task` – hand gestures
- `pose_landmarker_lite.task` – full-body pose for counting jumping jacks
  (fetched when the server starts, so it's ready before the alarm rings)

## Running the frontend

In a second terminal:

```bash
cd frontend
npm install      # first time only
npm run dev
```

Then open the URL Vite prints (usually http://localhost:5173). In dev, requests
to `/api` are proxied to the backend at `http://localhost:8000`, so start the
backend first.

## Using the alarm

1. Pick a time under **Wake me at** and choose a sound (built-in, or
   **Use my own sound…** to upload an audio file). **Preview** plays it briefly.
2. Click **Set alarm**. The card shows when it will ring and a countdown.
   You can **Cancel alarm** any time before it rings.
3. When it rings, a full-screen overlay appears with the live camera feed:
   - **Jumping jacks phase:** step back so your full body is visible. The
     skeleton turns **green** when you're open (arms above shoulders, feet
     apart) and **orange** when closed (arms down, feet together). One
     closed → open → closed cycle counts as one jack. The overlay shows
     `Jacks: n / 3` and warns "no body detected, step back" if it can't see you.
   - **Gesture phase:** once the jacks are done, hold up the off gesture
     until the bar fills. The overlay shows which gesture it currently sees.
4. The alarm stops and resets.

A ringing alarm **cannot** be cancelled from the UI. The only exception: if the
camera or a model fails to load, the overlay shows the error and a **Turn off**
button as a fallback, so the alarm can't ring forever.

## Configuration (`config.py`)

| Setting | Default | What it does |
| --- | --- | --- |
| `ALARM_OFF_GESTURE` | `"Victory"` | Gesture that stops the alarm after the jacks |
| `ALARM_HOLD_FRAMES` | `20` | Consecutive frames the gesture must be held (~0.7 s) |
| `JACKS_REQUIRED` | `3` | Jumping jacks needed before the gesture counts (used by both the web app and `main.py`) |
| `MIN_GESTURE_SCORE` | `0.6` | Confidence needed to accept a gesture |
| `CAMERA_INDEX` | `0` | Which webcam to use |
| `MIRROR_VIEW` | `True` | Flip the camera horizontally |

Valid gesture names: `Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Down`,
`Thumb_Up`, `Victory`, `ILoveYou`.

## Standalone stopwatch with jumping-jack alarm (optional)

`main.py` is a separate gesture-controlled stopwatch that runs in an OpenCV
window, with no frontend needed:

```bash
python main.py
```

- Show `TOGGLE_GESTURE` (default `Victory`) to start/stop the stopwatch.
- Press `a` to trigger a test alarm. It beeps until you do the required
  jumping jacks (`JACKS_REQUIRED`),
  then show `TOGGLE_GESTURE` to stop it.
- Optionally add `ALARM_SECONDS = 30` (for example) to `config.py` to have the
  alarm go off automatically when the stopwatch reaches that time.
- Keys: `r` = reset timer and jacks, `a` = test alarm, `q` = quit.

## Testing the jumping-jack counter on its own

```bash
python jumping_jack_detect.py
```

Opens a camera window showing the jack count. Press `Esc` to quit.

## Tips

- Good lighting and a plain background improve both pose and gesture detection.
- If jacks aren't counting, step further back – your ankles and wrists must be
  visible, and your feet need to be clearly wider than your shoulders when open.
