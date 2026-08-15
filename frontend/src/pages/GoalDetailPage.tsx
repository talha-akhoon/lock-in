import { ArrowLeft, Check, LockKeyhole, Pencil } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Pill,
  Progress,
} from '../components/primitives'
import { useGoalHistory } from '../hooks/queries'
import { CATEGORY_META, TRACKING_LABELS } from '../lib/categories'
import { formatAmount, formatDate, formatDateTime, goalValueLabel } from '../lib/format'
import type { Goal, ProgressEntry } from '../lib/types'
import { EditGoal } from './onboarding/GoalWizardPage'

function entryLabel(entry: ProgressEntry, goal: Goal): string {
  if (entry.completed === true) return 'Marked complete'
  if (entry.completed === false) return 'Marked incomplete'
  if (entry.manual_percentage !== null) return `Set to ${entry.manual_percentage}%`
  const unit = goal.unit ? ` ${goal.unit}` : ''
  if (entry.numeric_delta !== null) {
    const sign = Number(entry.numeric_delta) >= 0 ? '+' : ''
    return `${sign}${formatAmount(entry.numeric_delta)}${unit}`
  }
  if (entry.numeric_value !== null) return `Now ${formatAmount(entry.numeric_value)}${unit}`
  return 'Checked in'
}

export function GoalDetailPage() {
  const { goalId } = useParams()
  const history = useGoalHistory(goalId)
  const [editing, setEditing] = useState(false)

  if (history.isLoading) return <Loading label="Loading the goal" />
  if (history.isError) {
    const status = (history.error as { status?: number }).status
    return (
      <ErrorState
        title={status === 404 ? 'Goal not found' : 'Could not load this goal'}
        body={
          status === 404
            ? 'It may have been deleted, or it belongs to someone else.'
            : (history.error as Error).message
        }
      >
        <Link className="ghost" to="/goals">
          <ArrowLeft /> Back to my goals
        </Link>
      </ErrorState>
    )
  }

  const goal = history.data!.goal
  const entries = history.data!.entries
  const Icon = CATEGORY_META[goal.category]?.icon
  const complete = Boolean(goal.completed_at)

  return (
    <>
      <Link className="back-link" to="/goals">
        <ArrowLeft /> My goals
      </Link>
      <PageHeader
        eyebrow={CATEGORY_META[goal.category]?.label ?? goal.category}
        title={goal.title}
        description={goal.description ?? undefined}
      >
        <button className="ghost" onClick={() => setEditing(true)}>
          <Pencil /> {goal.locked_at ? 'Visibility' : 'Edit'}
        </button>
      </PageHeader>

      <section className="card goal-detail-head">
        <div className="goal-detail-score">
          <b>{Math.round(goal.progress_percentage)}%</b>
          <Progress value={goal.progress_percentage} />
          <span>{goalValueLabel(goal)}</span>
        </div>
        <div className="goal-detail-facts">
          {Icon && (
            <span>
              <Icon /> {CATEGORY_META[goal.category].label}
            </span>
          )}
          <span>{TRACKING_LABELS[goal.tracking_type]}</span>
          <Pill tone={goal.required ? undefined : 'warn'}>
            {goal.required ? 'Required' : 'Optional'}
          </Pill>
          {goal.visibility === 'PRIVATE' && (
            <Pill>
              <LockKeyhole /> Private
            </Pill>
          )}
          {complete && (
            <Pill tone="good">
              <Check /> Completed {formatDate(goal.completed_at!)}
            </Pill>
          )}
          {goal.locked_at && <Pill>Locked {formatDate(goal.locked_at)}</Pill>}
        </div>
      </section>

      {goal.children.length > 0 && (
        <section className="card">
          <div className="section-title">
            <div>
              <span>Breakdown</span>
              <h2>Steps</h2>
            </div>
          </div>
          {goal.children.map((child) => (
            <div className="subgoal" key={child.id}>
              <span>
                <Link to={`/goals/${child.id}`}>{child.title}</Link>
              </span>
              <Progress value={child.progress_percentage} tone="muted" />
              <b>{Math.round(child.progress_percentage)}%</b>
            </div>
          ))}
        </section>
      )}

      <div className="section-heading">
        <div>
          <span className="eyebrow">Evidence</span>
          <h2>Progress history</h2>
        </div>
      </div>
      {entries.length === 0 ? (
        <Empty
          title="No updates yet"
          body="Every check-in against this goal is recorded here, newest first."
        />
      ) : (
        <section className="people-list card">
          {entries.map((entry) => (
            <div className="history-item" key={entry.id}>
              <div>
                <b>{entryLabel(entry, goal)}</b>
                <span>{formatDate(entry.entry_date)}</span>
                {entry.note && <p>{entry.note}</p>}
                {entry.evidence_url && (
                  <a href={entry.evidence_url} target="_blank" rel="noreferrer">
                    Evidence
                  </a>
                )}
              </div>
              <time>{formatDateTime(entry.created_at)}</time>
            </div>
          ))}
        </section>
      )}

      {editing && <EditGoal goal={goal} onClose={() => setEditing(false)} />}
    </>
  )
}
