import { ChevronDown, ChevronUp, LockKeyhole, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Progress } from '../../components/primitives'
import { useReorderGoalSteps } from '../../hooks/queries'
import type { Goal } from '../../lib/types'
import { movedStepIds } from './stepOrder'

export function GoalSteps({
  parent,
  canDelete,
  onDelete,
  linkTitles,
}: {
  parent: Goal
  canDelete?: boolean
  onDelete?: (goal: Goal) => void
  linkTitles?: boolean
}) {
  const reorder = useReorderGoalSteps()
  const steps = parent.children
  const canReorder = steps.length > 1

  function move(step: Goal, direction: 'up' | 'down') {
    const orderedIds = movedStepIds(
      steps.map((child) => child.id),
      step.id,
      direction,
    )
    if (!orderedIds || reorder.isPending) return
    reorder.mutate({ parentId: parent.id, orderedIds })
  }

  return (
    <>
      {steps.map((child, index) => (
        <div className="subgoal" key={child.id}>
          <span>
            {child.visibility === 'PRIVATE' && <LockKeyhole aria-label="Private step" />}{' '}
            {linkTitles ? <Link to={`/goals/${child.id}`}>{child.title}</Link> : child.title}
          </span>
          <Progress value={child.progress_percentage} tone="muted" />
          <b>{Math.round(child.progress_percentage)}%</b>
          {(canReorder || (canDelete && onDelete)) && (
            <div className="subgoal-actions">
              {canReorder && (
                <>
                  <button
                    type="button"
                    className="icon-button tiny"
                    onClick={() => move(child, 'up')}
                    disabled={index === 0 || reorder.isPending}
                    aria-label={`Move ${child.title} up`}
                  >
                    <ChevronUp />
                  </button>
                  <button
                    type="button"
                    className="icon-button tiny"
                    onClick={() => move(child, 'down')}
                    disabled={index === steps.length - 1 || reorder.isPending}
                    aria-label={`Move ${child.title} down`}
                  >
                    <ChevronDown />
                  </button>
                </>
              )}
              {canDelete && onDelete && (
                <button
                  type="button"
                  className="icon-button tiny"
                  onClick={() => onDelete(child)}
                  aria-label={`Delete ${child.title}`}
                >
                  <Trash2 />
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </>
  )
}
