import { Check, Copy, LogOut, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ConfirmDialog } from '../components/Modal'
import { PwaSettings } from '../components/PwaSettings'
import { Avatar, Empty, Loading, PageHeader, Pill } from '../components/primitives'
import {
  useCreateMcpToken,
  useLogout,
  useMcpTokens,
  useRevokeMcpToken,
} from '../hooks/queries'
import { formatDateTime } from '../lib/format'
import type { McpToken } from '../lib/types'
import { useAuthContext } from '../layouts/authContext'

function mcpConfig(token: string) {
  return JSON.stringify(
    {
      mcpServers: {
        lockin: {
          url: `${window.location.origin}/mcp`,
          headers: { Authorization: `Bearer ${token}` },
        },
      },
    },
    null,
    2,
  )
}

export function SettingsPage() {
  const auth = useAuthContext()
  const logout = useLogout()
  const navigate = useNavigate()
  const tokens = useMcpTokens()
  const create = useCreateMcpToken()
  const revoke = useRevokeMcpToken()
  const [name, setName] = useState('Claude')
  const [issued, setIssued] = useState<string | null>(null)
  const [copied, setCopied] = useState<'token' | 'config' | 'url' | null>(null)
  const [error, setError] = useState('')
  const [revoking, setRevoking] = useState<McpToken | null>(null)

  async function issue() {
    setError('')
    setCopied(null)
    try {
      const row = await create.mutateAsync(name.trim() || 'Claude')
      setIssued(row.token ?? null)
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  return (
    <>
      <PageHeader eyebrow="Account" title="Settings" description="Your identity and session." />
      <section className="card settings-identity">
        <Avatar name={auth.user.display_name} url={auth.user.avatar_url} size="lg" />
        <div>
          <b>{auth.user.display_name}</b>
          <span>{auth.user.email}</span>
        </div>
        {auth.role && <Pill tone={auth.role === 'ADMIN' ? 'good' : undefined}>{auth.role}</Pill>}
      </section>

      <section className="card admin-section">
        <h2>Your commitment</h2>
        <div className="admin-row">
          <b>Team</b>
          <span>{auth.team?.name ?? 'None'}</span>
        </div>
        <div className="admin-row">
          <b>Goals locked</b>
          <span>{auth.goals_locked ? 'Yes' : 'Not yet'}</span>
        </div>
        {auth.goals_committed_at ? (
          <div className="admin-row">
            <b>Committed at</b>
            <span>{formatDateTime(auth.goals_committed_at)}</span>
          </div>
        ) : (
          auth.goals_due_at && (
            <div className="admin-row">
              <b>Goals due</b>
              <span>{formatDateTime(auth.goals_due_at)}</span>
            </div>
          )
        )}
      </section>

      <PwaSettings />

      <section className="card admin-section warn">
        <h2>Connect your LLM</h2>
        <p className="hint">
          Connecting shares your view — including teammates&apos; team-visible goals — with your LLM
          provider. Private goals stay in LockIn. The model can read your goals, see team-visible
          progress, add goals and sub-steps (even after the lock, until the challenge ends), edit
          your goals before the lock, and log today&apos;s check-in. Once locked it cannot change
          your wording or targets or remove a goal.
        </p>
        <h3>ChatGPT</h3>
        <p className="hint">
          ChatGPT custom connectors cannot use a pasted token. Add a connector, paste the MCP URL
          below, and choose OAuth. You will sign in to LockIn and approve access. The token ChatGPT
          receives appears below as “ChatGPT” — revoke it if it leaks.
        </p>
        <div className="invite-code mcp-secret">
          <b className="mono">{`${window.location.origin}/mcp`}</b>
          <button
            className="ghost"
            onClick={async () => {
              await navigator.clipboard?.writeText(`${window.location.origin}/mcp`)
              setCopied('url')
            }}
          >
            {copied === 'url' ? <Check /> : <Copy />} {copied === 'url' ? 'Copied' : 'Copy MCP URL'}
          </button>
        </div>
        <h3>Cursor and Claude</h3>
        <p className="hint">
          Create a personal token and paste the JSON config into Cursor or Claude Desktop. Revoke
          the token if the secret leaks.
        </p>
        <div className="form-row">
          <label>
            Token name
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={80}
              placeholder="e.g. Claude Desktop"
            />
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        <button className="primary" onClick={issue} disabled={create.isPending || !name.trim()}>
          <Plus /> {create.isPending ? 'Creating…' : 'New token'}
        </button>
      </section>

      {issued && (
        <div className="invite-code card mcp-secret">
          <span>Copy this token once — it cannot be shown again</span>
          <b className="mono">{issued}</b>
          <button
            className="ghost"
            onClick={async () => {
              await navigator.clipboard?.writeText(issued)
              setCopied('token')
            }}
          >
            {copied === 'token' ? <Check /> : <Copy />} {copied === 'token' ? 'Copied' : 'Copy'}
          </button>
          <pre className="mcp-config">{mcpConfig(issued)}</pre>
          <button
            className="ghost"
            onClick={async () => {
              await navigator.clipboard?.writeText(mcpConfig(issued))
              setCopied('config')
            }}
          >
            {copied === 'config' ? <Check /> : <Copy />}{' '}
            {copied === 'config' ? 'Copied config' : 'Copy Cursor / Claude config'}
          </button>
        </div>
      )}

      {tokens.isLoading ? (
        <Loading />
      ) : !tokens.data?.length ? (
        <Empty
          title="No MCP tokens yet"
          body="Create one above to connect your own LLM to LockIn."
        />
      ) : (
        <section className="card admin-section">
          <h2>Active tokens</h2>
          {tokens.data.map((token) => (
            <div className="admin-row mcp-token-row" key={token.id}>
              <b>{token.name}</b>
              <span className="mono">{token.prefix}…</span>
              <small>
                {token.last_used_at
                  ? `Last used ${formatDateTime(token.last_used_at)}`
                  : `Created ${formatDateTime(token.created_at)}`}
              </small>
              <button
                className="icon-button"
                aria-label={`Revoke ${token.prefix}`}
                onClick={() => setRevoking(token)}
              >
                <Trash2 />
              </button>
            </div>
          ))}
        </section>
      )}

      {revoking && (
        <ConfirmDialog
          title="Revoke this token?"
          body={`Anything still using ${revoking.prefix}… will lose access immediately.`}
          confirmLabel="Revoke"
          pending={revoke.isPending}
          onCancel={() => setRevoking(null)}
          onConfirm={async () => {
            await revoke.mutateAsync(revoking.id)
            if (issued?.startsWith(revoking.prefix)) setIssued(null)
            setRevoking(null)
          }}
        />
      )}

      <button
        className="danger"
        disabled={logout.isPending}
        onClick={async () => {
          await logout.mutateAsync()
          navigate('/login', { replace: true })
        }}
      >
        <LogOut /> Sign out
      </button>
    </>
  )
}
