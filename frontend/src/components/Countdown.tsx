import { LockKeyhole, Timer } from 'lucide-react'
import { useCountdown } from '../hooks/useCountdown'
import { formatRemaining } from '../lib/format'

export function Countdown({
  dueAt,
  locked,
}: {
  dueAt: string | null | undefined
  locked: boolean
}) {
  const remaining = useCountdown(locked ? null : dueAt)

  if (locked) {
    return (
      <div className="countdown locked">
        <LockKeyhole />
        <div>
          <b>Locked</b>
          <span>Your commitment is final</span>
        </div>
      </div>
    )
  }
  if (!remaining) return null
  return (
    <div className={remaining.days < 1 ? 'countdown urgent' : 'countdown'}>
      <Timer />
      <div>
        <b>{formatRemaining(remaining)}</b>
        <span>{remaining.expired ? 'Deadline passed' : 'until your goals lock'}</span>
      </div>
    </div>
  )
}
