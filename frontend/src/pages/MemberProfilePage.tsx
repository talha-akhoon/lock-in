import { ArrowLeft, Flame, LockKeyhole, TriangleAlert } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Heatmap } from '../components/Heatmap'
import {
  Avatar,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Pill,
  Progress,
} from '../components/primitives'
import { useMemberProfile } from '../hooks/queries'
import { CATEGORY_META, CATEGORY_ORDER } from '../lib/categories'
import { formatDate, goalValueLabel } from '../lib/format'
import { useAuthContext } from '../layouts/authContext'

export function MemberProfilePage() {
  const { userId } = useParams()
  const auth = useAuthContext()
  const profile = useMemberProfile(auth.team?.id, userId)

  if (profile.isLoading) return <Loading label="Loading the profile" />
  if (profile.isError) {
    const status = (profile.error as { status?: number }).status
    return (
      <ErrorState
        title={status === 404 ? 'Member not found' : 'Could not load this profile'}
        body={
          status === 404
            ? 'Nobody on your team matches that link. They may have been removed.'
            : (profile.error as Error).message
        }
      >
        <Link className="ghost" to="/team">
          <ArrowLeft /> Back to the team
        </Link>
      </ErrorState>
    )
  }

  const data = profile.data!
  const submitted = data.goals.length > 0 || data.private_committed > 0

  return (
    <>
      <Link className="back-link" to="/team">
        <ArrowLeft /> Team
      </Link>
      <PageHeader
        eyebrow={data.is_self ? 'Your profile' : 'Member profile'}
        title={data.user.display_name}
        description={`Joined ${formatDate(data.user.joined_at)}`}
      >
        <Pill tone={data.user.role === 'ADMIN' ? 'good' : undefined}>{data.user.role}</Pill>
      </PageHeader>

      <section className="card profile-score">
        <Avatar name={data.user.display_name} url={data.user.avatar_url} size="lg" />
        <b>{data.overall_progress}%</b>
        <div>
          <h2>Overall progress</h2>
          <Progress value={data.overall_progress} />
          <small>
            {data.goals_completed} of {data.goals_committed} goals complete
            {data.private_committed > 0 &&
              ` · ${data.private_completed}/${data.private_committed} private`}
          </small>
        </div>
        <span>
          <Flame /> {data.streak} day streak
        </span>
      </section>

      {!submitted && (
        <div className="nudge warn">
          <TriangleAlert />
          <div>
            <b>Goals not submitted</b>
            <span>
              {data.goals_locked
                ? 'The submission deadline passed with nothing committed.'
                : `Due ${formatDate(data.goals_due_at)}.`}
            </span>
          </div>
        </div>
      )}

      <Heatmap data={data.heatmap} title={data.is_self ? 'Your activity' : 'Daily activity'} />

      <section className="category-score-grid">
        {CATEGORY_ORDER.filter((category) => data.categories[category] !== undefined).map(
          (category) => {
            const Icon = CATEGORY_META[category].icon
            return (
              <div className="card" key={category}>
                <span>
                  <Icon /> {CATEGORY_META[category].label}
                </span>
                <b>{data.categories[category]}%</b>
                <Progress value={Number(data.categories[category])} />
              </div>
            )
          },
        )}
      </section>

      <div className="section-heading">
        <div>
          <span className="eyebrow">The commitment</span>
          <h2>{data.is_self ? 'Your goals' : 'Goals they can be held to'}</h2>
        </div>
      </div>

      {data.private_committed > 0 && !data.is_self && (
        <div className="hint">
          {data.private_committed} private {data.private_committed === 1 ? 'goal' : 'goals'} counted
          towards the score above, {data.private_completed} of them complete. Titles stay hidden.
        </div>
      )}

      {data.goals.length === 0 ? (
        <Empty
          title="Nothing visible here"
          body={
            data.private_committed > 0
              ? 'Every goal they committed to is private.'
              : 'No goals have been committed yet.'
          }
        />
      ) : (
        CATEGORY_ORDER.map((category) => {
          const items = data.goals.filter((goal) => goal.category === category)
          if (!items.length) return null
          const Icon = CATEGORY_META[category].icon
          return (
            <section className="goal-section" key={category}>
              <h2>
                <Icon /> {CATEGORY_META[category].label}
              </h2>
              {items.map((goal) => (
                <article className="goal-card card compact" key={goal.id}>
                  <div className="goal-main">
                    <div>
                      <h3>
                        {goal.visibility === 'PRIVATE' && <LockKeyhole />}{' '}
                        {data.is_self ? <Link to={`/goals/${goal.id}`}>{goal.title}</Link> : goal.title}
                      </h3>
                      {goal.description && <p>{goal.description}</p>}
                    </div>
                    <b>{Math.round(goal.progress_percentage)}%</b>
                  </div>
                  <Progress value={goal.progress_percentage} />
                  <div className="goal-meta">
                    <span>{goalValueLabel(goal)}</span>
                    <Pill tone={goal.required ? undefined : 'warn'}>
                      {goal.required ? 'Required' : 'Optional'}
                    </Pill>
                  </div>
                  {goal.children.map((child) => (
                    <div className="subgoal" key={child.id}>
                      <span>{child.title}</span>
                      <Progress value={child.progress_percentage} tone="muted" />
                      <b>{Math.round(child.progress_percentage)}%</b>
                    </div>
                  ))}
                </article>
              ))}
            </section>
          )
        })
      )}
    </>
  )
}
