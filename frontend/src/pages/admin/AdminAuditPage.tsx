import { Empty, Loading } from '../../components/primitives'
import { useAuditLogs } from '../../hooks/queries'
import { formatDateTime, formatPence } from '../../lib/format'
import type { AuditLog } from '../../lib/types'
import { useAuthContext } from '../../layouts/authContext'

const ACTION_LABELS: Record<string, string> = {
  INVITATION_CREATED: 'issued an invitation',
  INVITATION_REVOKED: 'revoked an invitation',
  MEMBER_REMOVED: 'removed a member',
  MEMBER_ROLE_CHANGED: 'changed a role',
  CHALLENGE_PUBLISHED: 'published the challenge',
  CHALLENGE_DATES_CHANGED: 'changed the challenge dates',
  CHALLENGE_FORFEIT_CHANGED: 'changed the forfeit',
  GOAL_UNLOCKED: 'reopened a commitment',
  GOAL_EDITED_UNDER_OVERRIDE: 'authorised a locked-goal edit',
}

function detail(row: AuditLog): string | null {
  const meta = row.metadata
  if (!meta) return null
  const parts = Object.entries(meta)
    .filter(([key]) => key !== 'user_id' && key !== 'goal_id')
    .map(([key, value]) => `${label(key)}: ${format(key, value)}`)
  return parts.length ? parts.join(' · ') : null
}

function label(key: string): string {
  if (key.endsWith('_pence')) return key.slice(0, -'_pence'.length).replace(/_/g, ' ')
  return key.replace(/_/g, ' ')
}

function format(key: string, value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (key.endsWith('_pence') && typeof value === 'number') return formatPence(value)
  if (typeof value === 'string' && ISO_TIMESTAMP.test(value)) return formatDateTime(value)
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const ISO_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T/

export function AdminAuditPage() {
  const auth = useAuthContext()
  const logs = useAuditLogs(auth.team?.id)

  if (logs.isLoading) return <Loading />
  if (!logs.data?.length) {
    return (
      <Empty
        title="Nothing recorded yet"
        body="Invitations, role changes, challenge amendments and commitment overrides all appear here."
      />
    )
  }

  return (
    <section className="card admin-section">
      <h2>Audit log</h2>
      <p className="hint">Newest first. Two hundred most recent actions.</p>
      {logs.data.map((row) => (
        <div className="audit-row" key={row.id}>
          <div>
            <b>
              {row.actor} {ACTION_LABELS[row.action] ?? row.action.toLowerCase().replace(/_/g, ' ')}
            </b>
            <span className="mono">{row.entity_type}</span>
            {detail(row) && <p>{detail(row)}</p>}
          </div>
          <time>{formatDateTime(row.created_at)}</time>
        </div>
      ))}
    </section>
  )
}
