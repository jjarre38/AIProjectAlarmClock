// Thin wrapper around the Python server. Every call resolves to the alarm
// status: { target: ISO string | null, ringing: boolean, sound: string }.

async function request(path, options) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const getStatus = () => request('/status')
export const setAlarm = (time, sound) =>
  request('/alarm', { method: 'POST', body: JSON.stringify({ time, sound }) })
export const cancelAlarm = () => request('/alarm', { method: 'DELETE' })
export const turnOff = () => request('/turn-off', { method: 'POST' })
