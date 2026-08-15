import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight, Ticket, Users } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { FieldError } from '../../components/primitives'
import { useCreateTeam, useRedeemInvitation } from '../../hooks/queries'
import { useAuthContext } from '../../layouts/authContext'

const teamSchema = z.object({
  name: z.string().trim().min(2, 'Give the team a name of at least 2 characters').max(255),
})

const codeSchema = z.object({
  code: z
    .string()
    .trim()
    .toUpperCase()
    .regex(/^[A-Z2-9]{4}-[A-Z2-9]{4}$/, 'Codes look like ABCD-EFGH'),
})

type Mode = 'choose' | 'create' | 'join'

export function StartPage() {
  const auth = useAuthContext()
  const [mode, setMode] = useState<Mode>('choose')

  // Already in a team: onboarding is done, wherever they landed from.
  if (auth.team) return <Navigate to="/dashboard" replace />

  return (
    <main className="onboarding">
      <div className="brand">
        <span>LI</span> LockIn
      </div>
      {mode === 'choose' && (
        <section className="onboarding-card card">
          <div className="contract-mark">
            <Users />
          </div>
          <div className="eyebrow">Getting started</div>
          <h1>Who are you locking in with?</h1>
          <p>
            LockIn only works with people who will actually hold you to it. Start a team and invite
            them, or join one you've been invited to.
          </p>
          <div className="choice-grid">
            <button className="choice" onClick={() => setMode('create')}>
              <Users />
              <b>Start a team</b>
              <span>You'll be the admin and set the challenge</span>
              <ArrowRight />
            </button>
            <button className="choice" onClick={() => setMode('join')}>
              <Ticket />
              <b>Join with a code</b>
              <span>Someone already sent you an invitation</span>
              <ArrowRight />
            </button>
          </div>
        </section>
      )}
      {mode === 'create' && <CreateTeamCard onBack={() => setMode('choose')} />}
      {mode === 'join' && <JoinTeamCard onBack={() => setMode('choose')} />}
    </main>
  )
}

function CreateTeamCard({ onBack }: { onBack: () => void }) {
  const createTeam = useCreateTeam()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.input<typeof teamSchema>>({ resolver: zodResolver(teamSchema) })

  return (
    <section className="onboarding-card card">
      <div className="eyebrow">Step 1 of 2</div>
      <h1>Name your team.</h1>
      <p>This is what everyone sees. Use something the group already calls itself.</p>
      <form
        onSubmit={handleSubmit(async ({ name }) => {
          try {
            await createTeam.mutateAsync(name.trim())
            navigate('/onboarding/challenge')
          } catch (reason) {
            setError((reason as Error).message)
          }
        })}
        noValidate
      >
        <label>
          Team name
          <input {...register('name')} placeholder="e.g. The Sunday Circle" autoFocus />
          <FieldError message={errors.name?.message} />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="ghost" onClick={onBack}>
            Back
          </button>
          <button className="primary" disabled={createTeam.isPending}>
            {createTeam.isPending ? 'Creating…' : 'Create team'} <ArrowRight />
          </button>
        </div>
      </form>
    </section>
  )
}

function JoinTeamCard({ onBack }: { onBack: () => void }) {
  const redeem = useRedeemInvitation()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.input<typeof codeSchema>>({ resolver: zodResolver(codeSchema) })

  return (
    <section className="onboarding-card card">
      <div className="contract-mark">
        <Ticket />
      </div>
      <div className="eyebrow">Private team</div>
      <h1>You've been invited.</h1>
      <p>Enter your invitation code to join the people who will hold you accountable.</p>
      <form
        onSubmit={handleSubmit(async ({ code }) => {
          try {
            await redeem.mutateAsync(code.trim().toUpperCase())
            navigate('/onboarding/welcome')
          } catch (reason) {
            setError((reason as Error).message)
          }
        })}
        noValidate
      >
        <label>
          Invitation code
          <input
            {...register('code')}
            placeholder="ABCD-EFGH"
            maxLength={9}
            autoFocus
            className="code-input"
          />
          <FieldError message={errors.code?.message} />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="ghost" onClick={onBack}>
            Back
          </button>
          <button className="primary" disabled={redeem.isPending}>
            {redeem.isPending ? 'Joining…' : 'Join team'} <ArrowRight />
          </button>
        </div>
      </form>
    </section>
  )
}
