import { zodResolver } from '@hookform/resolvers/zod'
import { Check, Send } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import { Empty, FieldError, Loading, Pill } from '../../components/primitives'
import { useChallenge, useUpdateChallenge } from '../../hooks/queries'
import { formatDate, formatPence } from '../../lib/format'

const schema = z
  .object({
    name: z.string().trim().min(2, 'Name the challenge').max(255),
    description: z.string().trim().max(2000).optional(),
    start_date: z.string().min(1, 'Pick a start date'),
    end_date: z.string().min(1, 'Pick an end date'),
    forfeit_pounds: z.coerce.number().min(0, 'Cannot be negative').max(100_000),
  })
  .refine((value) => value.end_date > value.start_date, {
    path: ['end_date'],
    message: 'The end date must be after the start date',
  })

type Values = z.input<typeof schema>
type Parsed = z.output<typeof schema>

const dayOf = (iso: string) => iso.slice(0, 10)

export function AdminChallengePage() {
  const challenge = useChallenge()
  const update = useUpdateChallenge(challenge.data?.id)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  if (challenge.isLoading) return <Loading />
  if (!challenge.data) {
    return (
      <Empty title="No challenge yet" body="Create one to set the window and the forfeit.">
        <Link className="primary" to="/onboarding/challenge">
          Create the challenge
        </Link>
      </Empty>
    )
  }

  const data = challenge.data
  const completed = data.status === 'COMPLETED'

  return (
    <>
      <section className="card admin-section">
        <h2>
          Current terms <Pill tone={data.status === 'ACTIVE' ? 'good' : undefined}>{data.status}</Pill>
        </h2>
        <div className="admin-row">
          <b>Window</b>
          <span>
            {formatDate(data.start_at)} → {formatDate(data.end_at)}
          </span>
        </div>
        <div className="admin-row">
          <b>Forfeit</b>
          <span>{formatPence(data.forfeit_amount_pence)}</span>
        </div>
        <div className="admin-row">
          <b>Goal submission window</b>
          <span>
            {data.goal_submission_days} days from joining — fixed once the challenge is created
          </span>
        </div>
      </section>

      {completed ? (
        <Empty
          title="This challenge is closed"
          body="A completed challenge cannot be edited. Its outcomes and forfeits are final."
        >
          <Link className="primary" to="/results">
            View results
          </Link>
        </Empty>
      ) : (
        <AmendForm
          key={data.id}
          defaults={{
            name: data.name,
            description: data.description ?? '',
            start_date: dayOf(data.start_at),
            end_date: dayOf(data.end_at),
            forfeit_pounds: data.forfeit_amount_pence / 100,
          }}
          isDraft={data.status === 'DRAFT'}
          pending={update.isPending}
          message={message}
          error={error}
          onSubmit={async (values, publish) => {
            setError('')
            setMessage('')
            try {
              await update.mutateAsync({
                name: values.name,
                description: values.description?.trim() || null,
                start_at: new Date(`${values.start_date}T00:00:00`).toISOString(),
                end_at: new Date(`${values.end_date}T23:59:59`).toISOString(),
                forfeit_amount_pence: Math.round(values.forfeit_pounds * 100),
                ...(publish ? { publish: true } : {}),
              })
              setMessage(publish ? 'Published to the team.' : 'Changes saved and recorded.')
            } catch (reason) {
              setError((reason as Error).message)
            }
          }}
        />
      )}
    </>
  )
}

function AmendForm({
  defaults,
  isDraft,
  pending,
  message,
  error,
  onSubmit,
}: {
  defaults: Values
  isDraft: boolean
  pending: boolean
  message: string
  error: string
  onSubmit: (values: Parsed, publish: boolean) => void
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values, unknown, Parsed>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  })

  return (
    <form
      className="card admin-section"
      onSubmit={handleSubmit((values) => onSubmit(values, false))}
      noValidate
    >
      <h2>Amend the challenge</h2>
      <p className="hint">
        Changing the dates or the forfeit affects everyone and is written to the audit log.
      </p>
      <label>
        Name
        <input {...register('name')} />
        <FieldError message={errors.name?.message} />
      </label>
      <label>
        Description
        <textarea {...register('description')} />
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
      <label>
        Forfeit per person (£)
        <input type="number" min={0} step="1" {...register('forfeit_pounds')} />
        <FieldError message={errors.forfeit_pounds?.message} />
      </label>
      {error && <p className="error">{error}</p>}
      {message && (
        <div className="success">
          <Check /> {message}
        </div>
      )}
      <div className="modal-actions">
        {isDraft && (
          <button
            type="button"
            className="ghost"
            disabled={pending}
            onClick={handleSubmit((values) => onSubmit(values, true))}
          >
            <Send /> Save and publish
          </button>
        )}
        <button className="primary" disabled={pending}>
          {pending ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </form>
  )
}
