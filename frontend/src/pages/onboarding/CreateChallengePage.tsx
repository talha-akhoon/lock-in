import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight, CalendarRange } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { FieldError } from '../../components/primitives'
import { useCreateChallenge } from '../../hooks/queries'
import { useAuthContext } from '../../layouts/authContext'

const challengeSchema = z
  .object({
    name: z.string().trim().min(2, 'Name the challenge').max(255),
    description: z.string().trim().max(2000).optional(),
    start_date: z.string().min(1, 'Pick a start date'),
    end_date: z.string().min(1, 'Pick an end date'),
    goal_submission_days: z.coerce
      .number()
      .int()
      .min(1, 'At least one day')
      .max(30, 'At most 30 days'),
    forfeit_pounds: z.coerce.number().min(0, 'Cannot be negative').max(100_000),
  })
  .refine((value) => value.end_date > value.start_date, {
    path: ['end_date'],
    message: 'The end date must be after the start date',
  })

type ChallengeFormValues = z.input<typeof challengeSchema>
type ChallengeFormParsed = z.output<typeof challengeSchema>

function isoDate(offsetDays: number): string {
  const date = new Date()
  date.setDate(date.getDate() + offsetDays)
  return date.toISOString().slice(0, 10)
}

/** A date input gives a bare day; the API wants an instant. */
function startOfDay(day: string): string {
  return new Date(`${day}T00:00:00`).toISOString()
}

function endOfDay(day: string): string {
  return new Date(`${day}T23:59:59`).toISOString()
}

export function CreateChallengePage() {
  const auth = useAuthContext()
  const create = useCreateChallenge(auth.team?.id)
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ChallengeFormValues, unknown, ChallengeFormParsed>({
    resolver: zodResolver(challengeSchema),
    defaultValues: {
      name: 'Six-Month Lock-In',
      description: '',
      start_date: isoDate(0),
      end_date: isoDate(183),
      goal_submission_days: 5,
      forfeit_pounds: 200,
    },
  })

  if (!auth.team) return <Navigate to="/onboarding/start" replace />
  if (auth.role !== 'ADMIN') return <Navigate to="/dashboard" replace />
  if (auth.challenge_id) return <Navigate to="/dashboard" replace />

  return (
    <main className="onboarding">
      <div className="brand">
        <span>LI</span> LockIn
      </div>
      <section className="onboarding-card card wide">
        <div className="contract-mark">
          <CalendarRange />
        </div>
        <div className="eyebrow">Step 2 of 2</div>
        <h1>Set the terms.</h1>
        <p>
          Everyone in {auth.team.name} gets the same window and the same forfeit. You can amend
          these later from the admin screens, and every change is recorded.
        </p>
        <form
          onSubmit={handleSubmit(async (values) => {
            try {
              await create.mutateAsync({
                name: values.name,
                description: values.description?.trim() || null,
                start_at: startOfDay(values.start_date),
                end_at: endOfDay(values.end_date),
                goal_submission_days: values.goal_submission_days,
                forfeit_amount_pence: Math.round(values.forfeit_pounds * 100),
              })
              navigate('/onboarding/welcome')
            } catch (reason) {
              setError((reason as Error).message)
            }
          })}
          noValidate
        >
          <label>
            Challenge name
            <input {...register('name')} />
            <FieldError message={errors.name?.message} />
          </label>
          <label>
            What is this about?
            <textarea {...register('description')} placeholder="Optional context for the team" />
          </label>
          <div className="form-row">
            <label>
              Starts
              <input type="date" {...register('start_date')} />
              <FieldError message={errors.start_date?.message} />
            </label>
            <label>
              Ends
              <input type="date" {...register('end_date')} />
              <FieldError message={errors.end_date?.message} />
            </label>
          </div>
          <div className="form-row">
            <label>
              Days to submit goals
              <input type="number" min={1} max={30} {...register('goal_submission_days')} />
              <FieldError message={errors.goal_submission_days?.message} />
            </label>
            <label>
              Forfeit per person (£)
              <input type="number" min={0} step="1" {...register('forfeit_pounds')} />
              <FieldError message={errors.forfeit_pounds?.message} />
            </label>
          </div>
          <p className="hint">
            Anyone who misses a required goal pays the forfeit to every other member.
          </p>
          {error && <p className="error">{error}</p>}
          <div className="modal-actions">
            <button className="primary" disabled={create.isPending}>
              {create.isPending ? 'Creating…' : 'Start the challenge'} <ArrowRight />
            </button>
          </div>
        </form>
      </section>
    </main>
  )
}
