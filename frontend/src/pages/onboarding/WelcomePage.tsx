import { ChevronRight } from 'lucide-react'
import { Link, Navigate } from 'react-router-dom'
import { Countdown } from '../../components/Countdown'
import { Loading } from '../../components/primitives'
import { useChallenge } from '../../hooks/queries'
import { formatDate, formatPence } from '../../lib/format'
import { useAuthContext } from '../../layouts/authContext'

export function WelcomePage() {
  const auth = useAuthContext()
  const challenge = useChallenge()

  if (!auth.team) return <Navigate to="/onboarding/start" replace />
  if (challenge.isLoading) return <Loading />
  if (!challenge.data) {
    return auth.role === 'ADMIN' ? (
      <Navigate to="/onboarding/challenge" replace />
    ) : (
      <Navigate to="/dashboard" replace />
    )
  }

  const { forfeit_amount_pence, goal_submission_days, start_at, end_at } = challenge.data
  return (
    <main className="onboarding">
      <div className="brand">
        <span>LI</span> LockIn
      </div>
      <section className="onboarding-card commitment card">
        <div className="eyebrow">Welcome to the lock-in</div>
        <h1>Choose carefully.</h1>
        <p>
          From {formatDate(start_at)} to {formatDate(end_at)} you're committing to measurable
          progress in the areas of life that matter.
        </p>
        <ul>
          <li>
            You have {goal_submission_days} {goal_submission_days === 1 ? 'day' : 'days'} to define
            your goals.
          </li>
          <li>After that, your commitment is locked and targets cannot be lowered.</li>
          <li>Complete every required goal — or the forfeit applies.</li>
        </ul>
        <div className="forfeit">
          <span>Current forfeit</span>
          <b>{formatPence(forfeit_amount_pence)}</b>
          <small>to every other member</small>
        </div>
        <Countdown dueAt={auth.goals_due_at} locked={auth.goals_locked} />
        <Link className="primary" to="/onboarding/goals">
          Start setting my goals <ChevronRight />
        </Link>
      </section>
    </main>
  )
}
