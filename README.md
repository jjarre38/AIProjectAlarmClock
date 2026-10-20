# AIProjectAlarmClock

A gesture-controlled alarm clock. The Python backend (FastAPI) owns the alarm and
watches the webcam; once the alarm rings, the only way to stop it is to show the
off gesture (`ALARM_OFF_GESTURE` in `config.py`, default `Victory`). The React
frontend displays the alarm state, lets you set the time, and plays the sound.

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- A webcam

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

The MediaPipe gesture model is downloaded to `models/` automatically on first run
if it isn't already there.

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

## Standalone stopwatch (optional)

`main.py` is a separate gesture-controlled stopwatch that runs in an OpenCV
window, with no frontend needed:

```bash
python main.py
```

Show the toggle gesture to start/stop. Press `r` to reset, `q` to quit.
