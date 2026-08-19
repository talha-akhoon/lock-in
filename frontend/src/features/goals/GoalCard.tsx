import { Check, ChevronRight, LockKeyhole, Pencil, Plus, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { InfoTip } from '../../components/InfoTip'
import { Pill, Progress } from '../../components/primitives'
import { StepHelp } from './StepHelp'
import { goalValueLabel } from '../../lib/format'
import { TRACKING_LABELS } from '../../lib/categories'
import type { Goal } from '../../lib/types'

export function GoalCard({
  goal,
  onEdit,
  onDelete,
  onAddChild,
  editable,
  canAddChild,
}: {
  goal: Goal
  onEdit?: (goal: Goal) => void
  onDelete?: (goal: Goal) => void
  onAddChild?: (goal: Goal) => void
  editable?: boolean
  // Adding a step is allowed even once locked; deleting/editing is not.
  canAddChild?: boolean
}) {
  const complete = Boolean(goal.completed_at)
  return (
    <article className={complete ? 'goal-card card complete' : 'goal-card card'}>
      <div className="goal-main">
        <div>
          <h3>
            {goal.visibility === 'PRIVATE' && <LockKeyhole aria-label="Private goal" />}{' '}
            <Link to={`/goals/${goal.id}`}>{goal.title}</Link>
            {complete && <Check className="tick" aria-label="Complete" />}
          </h3>
          {goal.description && <p>{goal.description}</p>}
        </div>
        <b>{Math.round(goal.progress_percentage)}%</b>
      </div>
      <Progress value={goal.progress_percentage} />
      <div className="goal-meta">
        <span>{TRACKING_LABELS[goal.tracking_type] ?? goal.tracking_type}</span>
        <span>{goalValueLabel(goal)}</span>
        <Pill tone={goal.required ? undefined : 'warn'}>
          {goal.required ? 'Required' : 'Optional'}
        </Pill>
        {goal.children.length > 0 && (
          <span>
            {goal.children.filter((child) => child.completed_at).length}/{goal.children.length}{' '}
            steps done
          </span>
        )}
      </div>

      {goal.children.map((child) => (
        <div className="subgoal" key={child.id}>
          <span>
            {child.visibility === 'PRIVATE' && <LockKeyhole />} {child.title}
          </span>
          <Progress value={child.progress_percentage} tone="muted" />
          <b>{Math.round(child.progress_percentage)}%</b>
          {editable && onDelete && (
            <button
              className="icon-button tiny"
              onClick={() => onDelete(child)}
              aria-label={`Delete ${child.title}`}
            >
              <Trash2 />
            </button>
          )}
        </div>
      ))}

      <footer className="goal-actions">
        <Link to={`/goals/${goal.id}`} className="ghost small">
          History <ChevronRight />
        </Link>
        {onEdit && (
          <button className="ghost small" onClick={() => onEdit(goal)}>
            <Pencil /> Edit
          </button>
        )}
        {canAddChild && onAddChild && !goal.parent_goal_id && (
          <span className="with-info">
            <button className="ghost small" onClick={() => onAddChild(goal)}>
              <Plus /> Add step
            </button>
            <InfoTip label="What is a step?">
              <StepHelp />
            </InfoTip>
          </span>
        )}
        {editable && onDelete && (
          <button className="ghost small danger-text" onClick={() => onDelete(goal)}>
            <Trash2 /> Delete
          </button>
        )}
      </footer>
    </article>
  )
}
