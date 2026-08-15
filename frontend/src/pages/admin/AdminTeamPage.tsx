import { Loading, Pill, Progress } from '../../components/primitives'
import { useChallenge, useCurrentTeam, useDashboard } from '../../hooks/queries'
import { formatDate, formatPence } from '../../lib/format'
import { useAuthContext } from '../../layouts/authContext'

export function AdminTeamPage() {
  const auth = useAuthContext()
  const team = useCurrentTeam()
  const challenge = useChallenge()
  const dashboard = useDashboard(challenge.data?.id)

  if (team.isLoading) return <Loading />

  const members = dashboard.data?.members ?? []
  const unsubmitted = members.filter((member) => !member.goals_submitted)

  return (
    <>
      <section className="card admin-section">
        <h2>{team.data?.name ?? auth.team?.name}</h2>
        <div className="admin-row">
          <b>Members</b>
          <span>{team.data?.member_count ?? members.length}</span>
        </div>
        <div className="admin-row">
          <b>Your role</b>
          <span>{team.data?.role ?? auth.role}</span>
        </div>
        <div className="admin-row">
          <b>Team ID</b>
          <span className="mono">{team.data?.id ?? auth.team?.id}</span>
        </div>
      </section>

      {challenge.data && (
        <section className="card admin-section">
          <h2>{challenge.data.name}</h2>
          <div className="admin-row">
            <b>Status</b>
            <Pill tone={challenge.data.status === 'ACTIVE' ? 'good' : undefined}>
              {challenge.data.status}
            </Pill>
          </div>
          <div className="admin-row">
            <b>Window</b>
            <span>
              {formatDate(challenge.data.start_at)} → {formatDate(challenge.data.end_at)}
            </span>
          </div>
          <div className="admin-row">
            <b>Day</b>
            <span>
              {challenge.data.day_number} of {challenge.data.total_days} ·{' '}
              {challenge.data.days_remaining} remaining
            </span>
          </div>
          <div className="admin-row">
            <b>Forfeit</b>
            <span>{formatPence(challenge.data.forfeit_amount_pence)} per person</span>
          </div>
          <div className="admin-row">
            <b>Team progress</b>
            <span>{dashboard.data?.team_progress ?? 0}%</span>
          </div>
          <Progress value={dashboard.data?.team_progress ?? 0} />
        </section>
      )}

      {unsubmitted.length > 0 && (
        <section className="card admin-section warn">
          <h2>Yet to commit</h2>
          {unsubmitted.map((member) => (
            <div className="admin-row" key={member.user_id}>
              <b>{member.display_name}</b>
              <span>{member.goals_locked ? 'Deadline passed' : 'Still in window'}</span>
              <Pill tone={member.goals_locked ? 'bad' : 'warn'}>
                {member.goals_locked ? 'Missed' : 'Pending'}
              </Pill>
            </div>
          ))}
        </section>
      )}
    </>
  )
}
