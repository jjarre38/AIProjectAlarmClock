// Built-in alarm sounds are synthesized with the Web Audio API, so there are
// no audio files to ship. A custom file the user picks plays through <audio>.

export const CUSTOM = 'custom'

// Each sound is a short pattern of notes that repeats every `period` ms.
// A note with `f2` slides from frequency f to f2 over its duration.
export const SOUNDS = {
  beep: {
    label: 'Classic beep',
    type: 'square',
    period: 700,
    notes: [
      { f: 880, at: 0, dur: 0.18 },
      { f: 880, at: 0.3, dur: 0.18 },
    ],
  },
  chime: {
    label: 'Soft chime',
    type: 'sine',
    period: 1800,
    notes: [
      { f: 523, at: 0, dur: 0.9 },
      { f: 659, at: 0.25, dur: 0.9 },
      { f: 784, at: 0.5, dur: 1.1 },
    ],
  },
  siren: {
    label: 'Siren',
    type: 'sawtooth',
    period: 1200,
    notes: [
      { f: 600, f2: 1000, at: 0, dur: 0.6 },
      { f: 1000, f2: 600, at: 0.6, dur: 0.6 },
    ],
  },
  pulse: {
    label: 'Digital pulse',
    type: 'triangle',
    period: 500,
    notes: [
      { f: 1200, at: 0, dur: 0.08 },
      { f: 1200, at: 0.12, dur: 0.08 },
      { f: 1200, at: 0.24, dur: 0.08 },
    ],
  },
}

let ctx

function getContext() {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)()
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

// Browsers only allow sound after the user has interacted with the page.
// Call this from a click handler (e.g. "Set alarm") so the alarm can ring later.
export function unlockAudio() {
  getContext()
}

function playOnce(def, output) {
  const ac = getContext()
  const t0 = ac.currentTime
  for (const n of def.notes) {
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    const start = t0 + n.at
    osc.type = def.type
    osc.frequency.setValueAtTime(n.f, start)
    if (n.f2) osc.frequency.linearRampToValueAtTime(n.f2, start + n.dur)
    gain.gain.setValueAtTime(0.0001, start)
    gain.gain.exponentialRampToValueAtTime(0.25, start + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, start + n.dur)
    osc.connect(gain).connect(output)
    osc.start(start)
    osc.stop(start + n.dur + 0.05)
  }
}

// Starts a sound on repeat. Returns a function that stops it immediately.
export function startSound(key, customUrl) {
  if (key === CUSTOM && customUrl) {
    const audio = new Audio(customUrl)
    audio.loop = true
    audio.play().catch(() => {})
    return () => {
      audio.pause()
      audio.currentTime = 0
    }
  }

  const def = SOUNDS[key] ?? SOUNDS.beep
  const ac = getContext()
  const master = ac.createGain()
  master.connect(ac.destination)
  playOnce(def, master)
  const id = setInterval(() => playOnce(def, master), def.period)

  return () => {
    clearInterval(id)
    try {
      master.disconnect() // cuts off any notes still ringing out
    } catch {
      /* already disconnected */
    }
  }
}
