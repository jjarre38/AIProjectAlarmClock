import { useEffect, useRef, useState } from 'react'
import { cancelAlarm, getStatus, setAlarm, turnOff } from './api'
import { CUSTOM, SOUNDS, startSound, unlockAudio } from './sounds'

const TIME_FORMAT = { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }

// Names used by the MediaPipe gesture model -> what to show the user.
const GESTURE_LABELS = {
  Closed_Fist: '✊ Closed fist',
  Open_Palm: '✋ Open palm',
  Pointing_Up: '☝️ Pointing up',
  Thumb_Down: '👎 Thumbs down',
  Thumb_Up: '👍 Thumbs up',
  Victory: '✌️ Victory',
  ILoveYou: '🤟 I love you',
}

const gestureLabel = (name) => GESTURE_LABELS[name] ?? name

function useNow() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

function formatRemaining(ms) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h) return `${h}h ${m}m`
  if (m) return `${m}m ${s}s`
  return `${s}s`
}

// Live view from the server's camera. The message behind the image shows
// until the first frame arrives, and a dropped stream is retried.
function CameraView({ ring }) {
  const [attempt, setAttempt] = useState(0)
  const [failed, setFailed] = useState(false)

  function handleError() {
    setFailed(true)
    setTimeout(() => setAttempt((n) => n + 1), 1000)
  }

  return (
    <div className="camera">
      <span className="camera-msg">
        {failed ? "Can't reach the camera feed, retrying…" : 'Starting camera…'}
      </span>
      <img
        key={attempt}
        src={`/api/camera?ring=${encodeURIComponent(ring)}&try=${attempt}`}
        alt="Camera view"
        onLoad={() => setFailed(false)}
        onError={handleError}
      />
    </div>
  )
}

export default function App() {
  const now = useNow()
  const [status, setStatus] = useState({ target: null, ringing: false, sound: 'beep' })
  const [online, setOnline] = useState(true)
  const [time, setTime] = useState('07:00')
  const [sound, setSound] = useState('beep')
  const [custom, setCustom] = useState(null) // { name, url }
  const [error, setError] = useState('')
  const previewStop = useRef(null)

  // Ask the Python server for the alarm state a couple of times a second.
  useEffect(() => {
    let alive = true
    async function poll() {
      try {
        const s = await getStatus()
        if (alive) {
          setStatus(s)
          setOnline(true)
        }
      } catch {
        if (alive) setOnline(false)
      }
    }
    poll()
    const id = setInterval(poll, 250)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  // Play the sound for as long as the server says the alarm is ringing.
  useEffect(() => {
    if (!status.ringing) return
    const key = status.sound === CUSTOM && !custom ? 'beep' : status.sound
    return startSound(key, custom?.url)
  }, [status.ringing, status.sound, custom])

  async function run(action) {
    setError('')
    try {
      setStatus(await action())
    } catch (e) {
      setError(e.message || 'Something went wrong')
    }
  }

  function handleSet() {
    unlockAudio()
    run(() => setAlarm(time, sound))
  }

  function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    if (custom) URL.revokeObjectURL(custom.url)
    setCustom({ name: file.name, url: URL.createObjectURL(file) })
    setSound(CUSTOM)
  }

  function handlePreview() {
    unlockAudio()
    previewStop.current?.()
    const stop = startSound(sound, custom?.url)
    previewStop.current = stop
    setTimeout(() => {
      stop()
      if (previewStop.current === stop) previewStop.current = null
    }, 2500)
  }

  const armed = Boolean(status.target) && !status.ringing
  const target = status.target ? new Date(status.target) : null

  return (
    <main className="app">
      <section className="card">
        <header className="card-head">
          <h1>Alarm</h1>
          {!online && <span className="badge badge-warn">Server offline</span>}
        </header>

        <p className="clock">{now.toLocaleTimeString([], { ...TIME_FORMAT, second: '2-digit' })}</p>

        <p className={`status ${armed ? 'status-armed' : ''}`}>
          {armed
            ? `Rings ${target.toLocaleString([], { weekday: 'short', ...TIME_FORMAT })} · in ${formatRemaining(target - now)}`
            : 'No alarm set'}
        </p>

        <div className="field">
          <label htmlFor="alarm-time">Wake me at</label>
          <input
            id="alarm-time"
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            disabled={armed}
          />
        </div>

        <div className="field">
          <label htmlFor="alarm-sound">Sound</label>
          <div className="row">
            <select
              id="alarm-sound"
              value={sound}
              onChange={(e) => setSound(e.target.value)}
              disabled={armed}
            >
              {Object.entries(SOUNDS).map(([key, def]) => (
                <option key={key} value={key}>
                  {def.label}
                </option>
              ))}
              {custom && <option value={CUSTOM}>Custom: {custom.name}</option>}
            </select>
            <button type="button" className="btn btn-ghost" onClick={handlePreview}>
              Preview
            </button>
          </div>
          <label className={`upload ${armed ? 'upload-disabled' : ''}`}>
            Use my own sound…
            <input type="file" accept="audio/*" onChange={handleFile} disabled={armed} hidden />
          </label>
        </div>

        {error && <p className="error">{error}</p>}

        {armed ? (
          <button type="button" className="btn btn-secondary" onClick={() => run(cancelAlarm)}>
            Cancel alarm
          </button>
        ) : (
          <button type="button" className="btn btn-primary" onClick={handleSet} disabled={!time || !online}>
            Set alarm
          </button>
        )}
      </section>

      {status.ringing && (
        <div className="overlay" role="alertdialog" aria-live="assertive" aria-label="Alarm ringing">
          <p className="overlay-time">{now.toLocaleTimeString([], TIME_FORMAT)}</p>
          <h2>Your alarm is going off</h2>
          {status.camera_error || !status.required_gesture ? (
            <>
              <p className="overlay-hint">
                {status.camera_error
                  ? `Camera unavailable: ${status.camera_error}`
                  : 'The server is running old code. Restart uvicorn to use gestures.'}
              </p>
              <button type="button" className="btn btn-off" onClick={() => run(turnOff)}>
                Turn off
              </button>
            </>
          ) : (
            <>
              <CameraView ring={status.target} />
              <p className="overlay-hint">
                Hold up <strong>{gestureLabel(status.required_gesture)}</strong> to turn it off
              </p>
              <div className="hold-bar">
                <div className="hold-fill" style={{ width: `${Math.round(status.progress * 100)}%` }} />
              </div>
              <p className="overlay-seen">
                Seeing: {status.gesture && status.gesture !== 'None' ? gestureLabel(status.gesture) : 'no gesture'}
              </p>
            </>
          )}
        </div>
      )}
    </main>
  )
}
