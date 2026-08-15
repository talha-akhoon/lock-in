import { ChevronRight, Flame, Trophy, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Countdown } from '../components/Countdown'
import { Avatar, ErrorState, Loading, Pill, Progress } from '../components/primitives'
import { useChallenge, useDashboard } from '../hooks/queries'
import { categoryLabel } from '../lib/categories'
import { formatDate } from '../lib/format'
import type { Category, MemberCard } from '../lib/types'
import { useAuthContext } from '../layouts/authContext'
import { NoChallengePage } from './NoChallengePage'

export function DashboardPage() {
  const auth = useAuthContext()
  const challenge = useChallenge()
  const dashboard = useDashboard(challenge.data?.id)

  if (challenge.isLoading) return <Loading label="Loading the challenge" />
  // The API answers 404 when the team has no challenge, which is a normal
  // state rather than a failure worth alarming anyone about.
  const notFound = (challenge.error as { status?: number } | null)?.status === 404
  if (challenge.isError && !notFound) {
    return (
      <ErrorState body={(challenge.error as Error).message}>
        <button className="ghost" onClick={() => challenge.refetch()}>
          Try again
        </button>
      </ErrorState>
    )
  }
  if (!challenge.data) return <NoChallengePage />
  if (dashboard.isLoading) return <Loading label="Loading the team" />

  const data = dashboard.data
  const completed = challenge.data.status === 'COMPLETED'
  const upcoming = challenge.data.status === 'UPCOMING'

  return (
    <>
      <section className="challenge-hero">
        <div>
          <div className="eyebrow">{completed ? 'Finished' : 'Current commitment'}</div>
          <h1>{challenge.data.name}</h1>
          <p>
            {upcoming
              ? `Starts ${formatDate(challenge.data.start_at)}`
              : `Day ${challenge.data.day_number} of ${challenge.data.total_days}`}
          </p>
        </div>
        <div className="days">
          <b>{challenge.data.days_remaining}</b>
          <span>days remaining</span>
        </div>
      </section>

      {completed && (
        <div className="nudge finished">
          <Trophy />
          <div>
            <b>The challenge is over</b>
            <span>See who finished and what is owed.</span>
          </div>
          <Link className="primary" to="/results">
            View results
          </Link>
        </div>
      )}

      {/* A finished challenge has no submission window left to count down to. */}
      {!completed && !auth.goals_locked && !auth.goals_committed_at && (
        <Countdown dueAt={auth.goals_due_at} locked={false} />
      )}

      {upcoming && (auth.goals_locked || auth.goals_committed_at) && (
        <div className="nudge">
          <TriangleAlert />
          <div>
            <b>Record your starting point</b>
            <span>Save where you are now on each goal before the challenge starts.</span>
          </div>
          <Link className="primary" to="/check-in">
            Starting point
          </Link>
        </div>
      )}

      <section className="team-progress card">
        <div className="section-title">
          <div>
            <span>Team progress</span>
            <h2>All in, together.</h2>
          </div>
          <b>{data?.team_progress ?? 0}%</b>
        </div>
        <Progress value={data?.team_progress ?? 0} />
      </section>

      <div className="section-heading">
        <div>
          <span className="eyebrow">The team</span>
          <h2>Everyone's commitment</h2>
        </div>
        <Link to="/team">
          View team <ChevronRight />
        </Link>
      </div>

      <section className="member-grid">
        {(data?.members ?? []).map((member, index) => (
          <MemberTile
            key={member.user_id}
            member={member}
            rank={index + 1}
            over={completed}
          />
        ))}
      </section>
    </>
  )
}

function MemberTile({
  member,
  rank,
  over,
}: {
  member: MemberCard
  rank: number
  /** The challenge has finished, so nothing can be committed any more. */
  over: boolean
}) {
  if (!member.goals_submitted) {
    const stillOpen = !over && !member.goals_locked
    return (
      <article className="member-card card unsubmitted">
        <div className="member-head">
          <Avatar name={member.display_name} url={member.avatar_url} />
          <div>
            <h3>{member.display_name}</h3>
            <span>{member.is_self ? 'You' : 'Yet to commit'}</span>
          </div>
        </div>
        <div className="missing">
          <TriangleAlert />
          <div>
            <b>Goals not submitted</b>
            <span>
              {over
                ? 'The challenge ended with nothing committed.'
                : member.goals_locked
                  ? 'The deadline passed with nothing committed.'
                  : 'Still inside the submission window.'}
            </span>
          </div>
        </div>
        <footer>
          {member.is_self && stillOpen ? (
            <Link className="primary small" to="/onboarding/goals">
              Set my goals
            </Link>
          ) : member.is_self ? null : (
            <Link to={`/team/members/${member.user_id}`}>
              View profile <ChevronRight />
            </Link>
          )}
        </footer>
      </article>
    )
  }

  return (
    <article className="member-card card">
      <div className="member-head">
        <Avatar name={member.display_name} url={member.avatar_url} />
        <div>
          <h3>{member.display_name}</h3>
          <span>
            #{rank} in the team{member.is_self ? ' · You' : ''}
          </span>
        </div>
        <b>{member.overall_progress}%</b>
      </div>
      <Progress value={member.overall_progress} />
      <div className="category-list">
        {Object.entries(member.categories).map(([name, progress]) => (
          <div key={name}>
            <span>{categoryLabel(name as Category)}</span>
            <b>{Math.round(Number(progress))}%</b>
          </div>
        ))}
      </div>
      <div className="goal-meta">
        <Pill>
          {member.goals_completed}/{member.goals_committed} done
        </Pill>
        {member.participant_status === 'FORFEIT_DUE' && <Pill tone="bad">Forfeit due</Pill>}
        {member.participant_status === 'COMPLETED' && <Pill tone="good">Finished</Pill>}
      </div>
      <footer>
        <span>
          <Flame /> {member.streak} day streak
        </span>
        <Link to={`/team/members/${member.user_id}`}>
          View profile <ChevronRight />
        </Link>
      </footer>
    </article>
  )
}
