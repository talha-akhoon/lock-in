import { CalendarCheck, Check, Flame } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Empty, ErrorState, Loading, PageHeader, Progress } from '../components/primitives'
import {
  buildCheckinPayload,
  checkinTargets,
  formStateAfterSave,
  type CheckinFormState,
} from '../features/checkin/payload'
import { useDayCheckin, useHeatmap, useSaveCheckin } from '../hooks/queries'
import { CATEGORY_META, CATEGORY_ORDER } from '../lib/categories'
import { formatAmount, isoToday } from '../lib/format'
import type { Goal } from '../lib/types'

/** Existing values are the starting point so a save is always a real change. */
function initialState(goals: Goal[], baseline: boolean): CheckinFormState {
  const state: CheckinFormState = {}
  for (const goal of checkinTargets(goals)) {
    if (goal.tracking_type === 'MILESTONE') state[goal.id] = Boolean(goal.completed_at)
    else if (goal.tracking_type === 'MANUAL')
      state[goal.id] = String(goal.manual_progress_percentage ?? 0)
    else if (goal.tracking_type === 'COUNT' && !baseline) state[goal.id] = ''
    // Never show the API's decimal padding in an input the member types into.
    else state[goal.id] = goal.current_value === null ? '' : formatAmount(goal.current_value)
  }
  return state
}

export function CheckInPage() {
  const [day, setDay] = useState(() => isoToday())
  const checkin = useDayCheckin(day)
  const heatmap = useHeatmap()
  const save = useSaveCheckin()
  const [state, setState] = useState<CheckinFormState>({})
  const [saved, setSaved] = useState<CheckinFormState>({})
  const [note, setNote] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const goals = useMemo(() => checkin.data?.goals ?? [], [checkin.data])
  const preStart = Boolean(checkin.data?.pre_start || heatmap.data?.pre_start)
  const hydratedDate = useRef<string | null>(null)

  useEffect(() => {
    if (heatmap.data?.pre_start && heatmap.data.today !== day) {
      setDay(heatmap.data.today)
    }
  }, [heatmap.data, day])

  useEffect(() => {
    if (!checkin.data) return
    if (hydratedDate.current === checkin.data.date) return
    hydratedDate.current = checkin.data.date
    const next = initialState(checkin.data.goals, checkin.data.pre_start)
    setState(next)
    setSaved(next)
    setNote(checkin.data.note ?? '')
    setMessage('')
    setError('')
  }, [checkin.data])

  const leaves = useMemo(() => checkinTargets(goals), [goals])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setMessage('')
    const payload = buildCheckinPayload(goals, state, {
      date: day,
      note,
      baseline: preStart,
      saved,
    })
    if (!payload.updates.length && !payload.note) {
      setError('Nothing to save yet — update a goal or leave a note.')
      return
    }
    try {
      await save.mutateAsync(payload)
      const next = formStateAfterSave(state, goals, preStart)
      setState(next)
      setSaved(next)
      setMessage(
        payload.updates.length
          ? `Saved. ${payload.updates.length} ${payload.updates.length === 1 ? 'goal' : 'goals'} updated.`
          : 'Note saved.',
      )
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={preStart ? 'Before kick-off' : 'Daily accountability'}
        title={preStart ? 'Starting point' : "Today's Check-In"}
        description={
          preStart
            ? 'Record where you are now on each goal. Progress during the challenge is measured from this.'
            : "How did you move forward? Leave the fields you didn't touch blank."
        }
      >
        {!preStart && (
          <label className="date-picker">
            Date
            <input
              type="date"
              value={day}
              max={heatmap.data?.today ?? isoToday()}
              min={heatmap.data?.start_date}
              onChange={(event) => setDay(event.target.value)}
            />
          </label>
        )}
      </PageHeader>

      {heatmap.data && !preStart && heatmap.data.streak > 0 && (
        <div className="streak-banner">
          <Flame />
          <div>
            <b>
              {heatmap.data.streak} day {heatmap.data.streak === 1 ? 'streak' : 'streak'}
            </b>
            <span>{heatmap.data.total_days_logged} days logged in total</span>
          </div>
        </div>
      )}

      {checkin.isLoading ? (
        <Loading label="Loading the day" />
      ) : checkin.isError ? (
        <ErrorState body={(checkin.error as Error).message} />
      ) : leaves.length === 0 ? (
        <Empty title="No goals to check in against" body="Set your goals first, then come back.">
          <Link className="primary" to="/onboarding/goals">
            Set my goals
          </Link>
        </Empty>
      ) : (
        <form className="checkin-form" onSubmit={submit}>
          {checkin.data?.exists && (
            <div className="hint">
              {preStart
                ? 'You already saved a starting point. Saving again updates it.'
                : "You can check in again. This save adds to or updates today's record."}
            </div>
          )}
          {CATEGORY_ORDER.map((category) => {
            const items = goals.filter((goal) => goal.category === category)
            if (!items.length) return null
            const Icon = CATEGORY_META[category].icon
            return (
              <section className="card checkin-category" key={category}>
                <h2>
                  <Icon /> {CATEGORY_META[category].label}
                </h2>
                {items.map((goal) =>
                  goal.children.length ? (
                    <div className="checkin-parent" key={goal.id}>
                      <div className="checkin-parent-head">
                        <b>{goal.title}</b>
                        <Progress value={goal.progress_percentage} tone="muted" />
                      </div>
                      {goal.children.map((child) => (
                        <CheckinRow
                          key={child.id}
                          goal={child}
                          value={state[child.id]}
                          baseline={preStart}
                          onChange={(value) => setState((prev) => ({ ...prev, [child.id]: value }))}
                        />
                      ))}
                    </div>
                  ) : (
                    <CheckinRow
                      key={goal.id}
                      goal={goal}
                      value={state[goal.id]}
                      baseline={preStart}
                      onChange={(value) => setState((prev) => ({ ...prev, [goal.id]: value }))}
                    />
                  ),
                )}
              </section>
            )
          })}

          <label className="note card">
            Notes
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="What did you work on? What got in the way?"
              maxLength={2000}
            />
          </label>

          {error && <p className="error">{error}</p>}
          {message && (
            <div className="success">
              <Check /> {message}
            </div>
          )}
          <button className="primary save-checkin" disabled={save.isPending}>
            <CalendarCheck />{' '}
            {save.isPending ? 'Saving…' : preStart ? 'Save starting point' : "Save today's progress"}
          </button>
        </form>
      )}
    </>
  )
}

function CheckinRow({
  goal,
  value,
  baseline,
  onChange,
}: {
  goal: Goal
  value: string | boolean | undefined
  baseline?: boolean
  onChange: (value: string | boolean) => void
}) {
  const label = `${goal.title}${goal.unit ? ` (${goal.unit})` : ''}`
  return (
    <div className="checkin-row">
      <div>
        <b>{goal.title}</b>
        <span>{describe(goal, baseline)}</span>
      </div>
      {goal.tracking_type === 'MILESTONE' ? (
        <input
          type="checkbox"
          aria-label={label}
          checked={value === true}
          onChange={(event) => onChange(event.target.checked)}
        />
      ) : goal.tracking_type === 'MANUAL' ? (
        <input
          type="number"
          aria-label={label}
          min={0}
          max={100}
          step={1}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <input
          type="number"
          aria-label={label}
          step="any"
          placeholder={goal.tracking_type === 'COUNT' && !baseline ? '+0' : 'No update'}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </div>
  )
}

function describe(goal: Goal, baseline?: boolean): string {
  if (goal.tracking_type === 'MILESTONE') {
    return goal.completed_at
      ? 'Complete'
      : baseline
        ? 'Tick if this is already done'
        : 'Tick when done'
  }
  if (goal.tracking_type === 'MANUAL') {
    return baseline
      ? `Currently ${goal.manual_progress_percentage ?? 0}% — set where you are now`
      : `Currently ${goal.manual_progress_percentage ?? 0}% — set the new percentage`
  }
  if (goal.tracking_type === 'COUNT') {
    return baseline
      ? `${formatAmount(goal.current_value)} of ${formatAmount(goal.target_value)} — how many you already have`
      : `${formatAmount(goal.current_value)} of ${formatAmount(goal.target_value)} — add today's amount`
  }
  const current = formatAmount(goal.current_value ?? goal.baseline_value)
  return `Currently ${current}, target ${formatAmount(goal.target_value)}`
}
