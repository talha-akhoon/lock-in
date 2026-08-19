import { ArrowLeft, ArrowRight, Check, LockKeyhole, Plus, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ConfirmDialog } from '../../components/Modal'
import { Countdown } from '../../components/Countdown'
import { Empty, Loading, Pill, Progress } from '../../components/primitives'
import { GoalForm } from '../../features/goals/GoalForm'
import { GoalCard } from '../../features/goals/GoalCard'
import {
  useChallenge,
  useCommitGoals,
  useCreateGoal,
  useDeleteGoal,
  useMyGoals,
  useUpdateGoal,
} from '../../hooks/queries'
import { CATEGORY_META, CATEGORY_ORDER } from '../../lib/categories'
import { formatPence } from '../../lib/format'
import type { Category, Goal, GoalInput } from '../../lib/types'
import { useAuthContext } from '../../layouts/authContext'

type Step = Category | 'REVIEW'
const STEPS: Step[] = [...CATEGORY_ORDER, 'REVIEW']

export function GoalWizardPage() {
  const auth = useAuthContext()
  const goals = useMyGoals()
  const challenge = useChallenge()
  const [stepIndex, setStepIndex] = useState(0)

  if (!auth.team) return <Navigate to="/onboarding/start" replace />
  if (!auth.challenge_id) return <Navigate to="/dashboard" replace />
  // A finished challenge cannot be committed to, whatever the lock says.
  if (auth.challenge_status === 'COMPLETED') return <Navigate to="/results" replace />
  if (goals.isLoading) return <Loading label="Loading your goals" />
  if (goals.data?.goals_locked) return <Navigate to="/goals" replace />

  const step = STEPS[stepIndex]
  const all = goals.data?.goals ?? []

  return (
    <main className="wizard">
      <header className="wizard-head">
        <div className="brand">
          <span>LI</span> LockIn
        </div>
        <Countdown dueAt={auth.goals_due_at} locked={false} />
      </header>

      <ol className="wizard-steps">
        {STEPS.map((item, index) => {
          const count = item === 'REVIEW' ? all.length : all.filter((g) => g.category === item).length
          const label = item === 'REVIEW' ? 'Review' : CATEGORY_META[item].label
          return (
            <li key={item} className={index === stepIndex ? 'current' : index < stepIndex ? 'done' : ''}>
              <button onClick={() => setStepIndex(index)}>
                <span>{label}</span>
                {item !== 'REVIEW' && count > 0 && <b>{count}</b>}
              </button>
            </li>
          )
        })}
      </ol>

      {step === 'REVIEW' ? (
        <ReviewStep goals={all} onBack={() => setStepIndex(stepIndex - 1)} />
      ) : (
        <CategoryStep
          category={step}
          goals={all.filter((goal) => goal.category === step)}
          forfeitPence={challenge.data?.forfeit_amount_pence ?? 0}
          onBack={stepIndex > 0 ? () => setStepIndex(stepIndex - 1) : undefined}
          onNext={() => setStepIndex(stepIndex + 1)}
          nextLabel={stepIndex === STEPS.length - 2 ? 'Review commitment' : 'Next area'}
        />
      )}
    </main>
  )
}

function CategoryStep({
  category,
  goals,
  forfeitPence,
  onBack,
  onNext,
  nextLabel,
}: {
  category: Category
  goals: Goal[]
  forfeitPence: number
  onBack?: () => void
  onNext: () => void
  nextLabel: string
}) {
  const meta = CATEGORY_META[category]
  const Icon = meta.icon
  const create = useCreateGoal()
  const remove = useDeleteGoal()
  const [composing, setComposing] = useState(false)
  const [parent, setParent] = useState<Goal | null>(null)
  const [editing, setEditing] = useState<Goal | null>(null)
  const [deleting, setDeleting] = useState<Goal | null>(null)
  const [error, setError] = useState<string | null>(null)

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
    <section className="wizard-body">
      <div className="wizard-title">
        <div className="category-mark">
          <Icon />
        </div>
        <div>
          <span className="eyebrow">{meta.label}</span>
          <h1>What does progress look like here?</h1>
          <p>{meta.prompt}</p>
        </div>
      </div>

      {goals.length === 0 ? (
        <Empty
          title={`No ${meta.label} goals yet`}
          body="You can skip an area entirely — but a required goal you do add must be finished, or the forfeit applies."
        >
          <button className="primary" onClick={() => setComposing(true)}>
            <Plus /> Add a goal
          </button>
        </Empty>
      ) : (
        <>
          <div className="wizard-goals">
            {goals.map((goal) => (
              <GoalCard
                key={goal.id}
                goal={goal}
                editable
                canAddChild
                onEdit={setEditing}
                onDelete={setDeleting}
                onAddChild={(target) => {
                  setParent(target)
                  setComposing(true)
                }}
              />
            ))}
          </div>
          <button className="ghost add-another" onClick={() => setComposing(true)}>
            <Plus /> Add another {meta.label} goal
          </button>
        </>
      )}

      <p className="hint">
        Required goals decide the {formatPence(forfeitPence)} forfeit. Optional ones only affect your
        percentage.
      </p>

      <div className="wizard-actions">
        {onBack ? (
          <button className="ghost" onClick={onBack}>
            <ArrowLeft /> Back
          </button>
        ) : (
          <span />
        )}
        <button className="primary" onClick={onNext}>
          {nextLabel} <ArrowRight />
        </button>
      </div>

      {composing && (
        <GoalForm
          category={category}
          parent={parent ?? undefined}
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
      {editing && (
        <EditGoal goal={editing} onClose={() => setEditing(null)} />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete this goal?"
          body={`“${deleting.title}” and any steps under it will be removed. You can add it back until your commitment locks.`}
          confirmLabel="Delete goal"
          pending={remove.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            await remove.mutateAsync(deleting.id)
            setDeleting(null)
          }}
        />
      )}
    </section>
  )
}

export function EditGoal({ goal, onClose }: { goal: Goal; onClose: () => void }) {
  const update = useUpdateGoal(goal.id)
  const [error, setError] = useState<string | null>(null)
  return (
    <GoalForm
      goal={goal}
      lockedFields={Boolean(goal.locked_at)}
      pending={update.isPending}
      error={error}
      onClose={onClose}
      onSubmit={async (input) => {
        setError(null)
        try {
          await update.mutateAsync(
            goal.locked_at ? { visibility: input.visibility } : input,
          )
          onClose()
        } catch (reason) {
          setError((reason as Error).message)
        }
      }}
    />
  )
}

function ReviewStep({ goals, onBack }: { goals: Goal[]; onBack: () => void }) {
  const commit = useCommitGoals()
  const navigate = useNavigate()
  const [accepted, setAccepted] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const required = goals.filter((goal) => goal.required)
  const emptyCategories = CATEGORY_ORDER.filter(
    (category) => !goals.some((goal) => goal.category === category),
  )

  return (
    <section className="wizard-body review">
      <div className="wizard-title">
        <div className="category-mark">
          <ShieldAlert />
        </div>
        <div>
          <span className="eyebrow">The contract</span>
          <h1>This is what you're committing to.</h1>
          <p>
            Read it once more. After you commit, targets, titles and structure are final for the
            whole challenge.
          </p>
        </div>
      </div>

      {goals.length === 0 ? (
        <Empty
          title="You haven't set any goals"
          body="Go back and add at least one goal before committing."
        >
          <button className="primary" onClick={onBack}>
            <ArrowLeft /> Back to goals
          </button>
        </Empty>
      ) : (
        <>
          <div className="review-summary card">
            <div>
              <b>{goals.length}</b>
              <span>{goals.length === 1 ? 'goal' : 'goals'} total</span>
            </div>
            <div>
              <b>{required.length}</b>
              <span>required to avoid the forfeit</span>
            </div>
            <div>
              <b>{goals.filter((goal) => goal.visibility === 'PRIVATE').length}</b>
              <span>private to you</span>
            </div>
          </div>

          {emptyCategories.length > 0 && (
            <p className="hint">
              Nothing set for {emptyCategories.map((item) => CATEGORY_META[item].label).join(', ')}.
              That's allowed, but those areas won't count towards your progress.
            </p>
          )}

          {CATEGORY_ORDER.map((category) => {
            const items = goals.filter((goal) => goal.category === category)
            if (!items.length) return null
            const Icon = CATEGORY_META[category].icon
            return (
              <section className="review-group card" key={category}>
                <h2>
                  <Icon /> {CATEGORY_META[category].label}
                </h2>
                {items.map((goal) => (
                  <div className="review-row" key={goal.id}>
                    <div>
                      <b>{goal.title}</b>
                      {goal.children.length > 0 && (
                        <span>{goal.children.map((child) => child.title).join(' · ')}</span>
                      )}
                    </div>
                    <Pill tone={goal.required ? undefined : 'warn'}>
                      {goal.required ? 'Required' : 'Optional'}
                    </Pill>
                    {goal.visibility === 'PRIVATE' && (
                      <Pill>
                        <LockKeyhole /> Private
                      </Pill>
                    )}
                    <Progress value={goal.progress_percentage} tone="muted" />
                  </div>
                ))}
              </section>
            )
          })}

          <label className="accept card">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(event) => setAccepted(event.target.checked)}
            />
            <span>
              I understand these goals are final, that my team can see everything except my private
              goals, and that missing a required goal means paying the forfeit.
            </span>
          </label>

          {error && <p className="error">{error}</p>}

          <div className="wizard-actions">
            <button className="ghost" onClick={onBack}>
              <ArrowLeft /> Back
            </button>
            <button
              className="danger"
              disabled={!accepted || commit.isPending}
              onClick={() => setConfirming(true)}
            >
              <Check /> I'm committing to this
            </button>
          </div>
        </>
      )}

      {confirming && (
        <ConfirmDialog
          title="Lock in your commitment?"
          body="This cannot be undone without an admin override. Your goals become read-only for the rest of the challenge."
          confirmLabel="Lock it in"
          pending={commit.isPending}
          error={error}
          onCancel={() => setConfirming(false)}
          onConfirm={async () => {
            setError(null)
            try {
              await commit.mutateAsync()
              navigate('/dashboard')
            } catch (reason) {
              setError((reason as Error).message)
              setConfirming(false)
            }
          }}
        />
      )}
    </section>
  )
}
