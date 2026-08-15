import { Check, Copy, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { ConfirmDialog } from '../../components/Modal'
import { Empty, FieldError, Loading, Pill } from '../../components/primitives'
import {
  useCreateInvitation,
  useInvitations,
  useRevokeInvitation,
} from '../../hooks/queries'
import { formatDate, formatDateTime } from '../../lib/format'
import type { Invitation } from '../../lib/types'
import { useAuthContext } from '../../layouts/authContext'

export function AdminInvitationsPage() {
  const auth = useAuthContext()
  const invitations = useInvitations(auth.team?.id)
  const create = useCreateInvitation(auth.team?.id)
  const revoke = useRevokeInvitation(auth.team?.id)
  const [maxUses, setMaxUses] = useState('1')
  const [expires, setExpires] = useState('')
  const [issued, setIssued] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')
  const [revoking, setRevoking] = useState<Invitation | null>(null)

  const uses = Number(maxUses)
  const usesValid = Number.isInteger(uses) && uses >= 1 && uses <= 100

  async function issue() {
    setError('')
    setCopied(false)
    try {
      const invitation = await create.mutateAsync({
        max_uses: uses,
        expires_at: expires ? new Date(`${expires}T23:59:59`).toISOString() : null,
      })
      setIssued(invitation.code ?? null)
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  return (
    <>
      <section className="card admin-section">
        <h2>Issue an invitation</h2>
        <p className="hint">
          The full code is shown once and never stored. Only the first four characters are kept, so
          you can tell codes apart later.
        </p>
        <div className="form-row">
          <label>
            Maximum uses
            <input
              type="number"
              min={1}
              max={100}
              value={maxUses}
              onChange={(event) => setMaxUses(event.target.value)}
            />
            <FieldError message={usesValid ? undefined : 'Between 1 and 100'} />
          </label>
          <label>
            Expires (optional)
            <input
              type="date"
              value={expires}
              onChange={(event) => setExpires(event.target.value)}
            />
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        <button className="primary" onClick={issue} disabled={create.isPending || !usesValid}>
          <Plus /> {create.isPending ? 'Creating…' : 'New invitation'}
        </button>
      </section>

      {issued && (
        <div className="invite-code card">
          <span>Share this code once — it cannot be shown again</span>
          <b>{issued}</b>
          <button
            className="ghost"
            onClick={async () => {
              await navigator.clipboard?.writeText(issued)
              setCopied(true)
            }}
          >
            {copied ? <Check /> : <Copy />} {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      )}

      {invitations.isLoading ? (
        <Loading />
      ) : !invitations.data?.length ? (
        <Empty title="No invitations yet" body="Issue one above to bring someone into the team." />
      ) : (
        <section className="card admin-section">
          <h2>Invitation codes</h2>
          {invitations.data.map((invitation) => {
            const exhausted =
              invitation.max_uses !== null && invitation.use_count >= invitation.max_uses
            const expired =
              invitation.expires_at !== null && new Date(invitation.expires_at) < new Date()
            const dead = Boolean(invitation.revoked_at) || exhausted || expired
            return (
              <div className="admin-row invite-row" key={invitation.id}>
                <b className="mono">{invitation.code_prefix}-••••</b>
                <span>
                  {invitation.use_count} / {invitation.max_uses ?? '∞'} uses ·{' '}
                  {invitation.expires_at
                    ? `expires ${formatDate(invitation.expires_at)}`
                    : 'no expiry'}
                </span>
                <Pill tone={dead ? 'bad' : 'good'}>
                  {invitation.revoked_at
                    ? 'Revoked'
                    : exhausted
                      ? 'Used up'
                      : expired
                        ? 'Expired'
                        : 'Active'}
                </Pill>
                <small>{formatDateTime(invitation.created_at)}</small>
                {!dead && (
                  <button
                    className="icon-button"
                    aria-label={`Revoke ${invitation.code_prefix}`}
                    onClick={() => setRevoking(invitation)}
                  >
                    <Trash2 />
                  </button>
                )}
              </div>
            )
          })}
        </section>
      )}

      {revoking && (
        <ConfirmDialog
          title="Revoke this invitation?"
          body={`Anyone still holding ${revoking.code_prefix}-•••• will no longer be able to join.`}
          confirmLabel="Revoke"
          pending={revoke.isPending}
          onCancel={() => setRevoking(null)}
          onConfirm={async () => {
            await revoke.mutateAsync(revoking.id)
            setRevoking(null)
          }}
        />
      )}
    </>
  )
}
