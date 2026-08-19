import { LockKeyhole, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Countdown } from '../components/Countdown'
import { ConfirmDialog } from '../components/Modal'
import { Empty, ErrorState, Loading, PageHeader, Progress } from '../components/primitives'
import { GoalCard } from '../features/goals/GoalCard'
import { GoalForm } from '../features/goals/GoalForm'
import { EditGoal } from './onboarding/GoalWizardPage'
import { useCreateGoal, useDeleteGoal, useMyGoals } from '../hooks/queries'
import { CATEGORY_META, CATEGORY_ORDER } from '../lib/categories'
import type { Goal, GoalInput } from '../lib/types'
import { useAuthContext } from '../layouts/authContext'

export function GoalsPage() {
  const auth = useAuthContext()
  const goals = useMyGoals()
  const create = useCreateGoal()
  const remove = useDeleteGoal()
  const [composing, setComposing] = useState(false)
  const [parent, setParent] = useState<Goal | null>(null)
  const [editing, setEditing] = useState<Goal | null>(null)
  const [deleting, setDeleting] = useState<Goal | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (goals.isLoading) return <Loading label="Loading your goals" />
  if (goals.isError) return <ErrorState body={(goals.error as Error).message} />

  const data = goals.data
  const locked = Boolean(data?.goals_locked)
  // Adding only strengthens a commitment, so it stays open after the lock and
  // closes only once the challenge is over.
  const challengeOver = auth.challenge_status === 'COMPLETED'
  const canAdd = !challengeOver
  const items = data?.goals ?? []

  async function submit(input: GoalInput) {
    setError(null)
    try {
      await create.mutateAsync(input)
      setComposing(false)
      setParent(null)
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Your commitment"
        title="My Goals"
        description={
          locked
            ? 'Your commitment is locked. Now go finish it.'
            : 'Choose carefully. These goals become your contract.'
        }
      >
        {canAdd && (
          <button className="primary" onClick={() => setComposing(true)}>
            <Plus /> Add goal
          </button>
        )}
      </PageHeader>

      {locked ? (
        <div className="locked-banner">
          <LockKeyhole />
          <div>
            <b>Your commitment is locked</b>
            <span>
              {challengeOver
                ? 'This challenge has ended.'
                : 'You can still add goals and steps, and reorder steps, but existing ones can no longer be changed or removed.'}
            </span>
          </div>
        </div>
      ) : (
        <Countdown dueAt={auth.goals_due_at} locked={false} />
      )}

      {items.length > 0 && (
        <section className="team-progress card">
          <div className="section-title">
            <div>
              <span>Overall</span>
              <h2>Your progress</h2>
            </div>
            <b>{data?.overall_progress ?? 0}%</b>
          </div>
          <Progress value={data?.overall_progress ?? 0} />
        </section>
      )}

      {items.length === 0 ? (
        <Empty
          title="No goals yet"
          body={
            locked
              ? 'Your window closed before you added any. You can still add goals — each one joins your commitment as you add it.'
              : 'Start with the area that matters most. The wizard walks you through all five.'
          }
        >
          {locked ? (
            // The wizard redirects away once locked, so adding is the real path.
            canAdd && (
              <button className="primary" onClick={() => setComposing(true)}>
                <Plus /> Add goal
              </button>
            )
          ) : (
            <Link className="primary" to="/onboarding/goals">
              Open the goal wizard
            </Link>
          )}
        </Empty>
      ) : (
        CATEGORY_ORDER.map((category) => {
          const inCategory = items.filter((goal) => goal.category === category)
          if (!inCategory.length) return null
          const Icon = CATEGORY_META[category].icon
          return (
            <section className="goal-section" key={category}>
              <h2>
                <Icon /> {CATEGORY_META[category].label}
              </h2>
              {inCategory.map((goal) => (
                <GoalCard
                  key={goal.id}
                  goal={goal}
                  editable={!locked}
                  canAddChild={canAdd}
                  onEdit={setEditing}
                  onDelete={locked ? undefined : setDeleting}
                  onAddChild={(target) => {
                    setParent(target)
                    setComposing(true)
                  }}
                />
              ))}
            </section>
          )
        })
      )}

      {!locked && items.length > 0 && (
        <div className="commit-panel">
          <div>
            <h3>Ready to make it official?</h3>
            <p>Once you commit, you cannot lower or remove these goals.</p>
          </div>
          <Link className="danger" to="/onboarding/goals">
            Review and commit
          </Link>
        </div>
      )}

      {composing && (
        <GoalForm
          parent={parent ?? undefined}
          lockedNotice={locked}
          onSubmit={submit}
          onClose={() => {
            setComposing(false)
            setParent(null)
            setError(null)
          }}
          pending={create.isPending}
          error={error}
        />
      )}
      {editing && <EditGoal goal={editing} onClose={() => setEditing(null)} />}
      {deleting && (
        <ConfirmDialog
          title="Delete this goal?"
          body={`“${deleting.title}” and any steps under it will be removed.`}
          confirmLabel="Delete goal"
          pending={remove.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            await remove.mutateAsync(deleting.id)
            setDeleting(null)
          }}
        />
      )}
    </>
  )
}
