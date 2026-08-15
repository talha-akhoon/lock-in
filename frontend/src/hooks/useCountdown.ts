import { useEffect, useState } from 'react'
import { timeRemaining, type Remaining } from '../lib/format'

/** Ticks once a second so a deadline on screen stays honest. */
export function useCountdown(target: string | null | undefined): Remaining | null {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    if (!target) return
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [target])
  if (!target) return null
  return timeRemaining(target, now)
}
