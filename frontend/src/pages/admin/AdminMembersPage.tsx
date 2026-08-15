import { LockKeyholeOpen, ShieldCheck, UserMinus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ConfirmDialog } from '../../components/Modal'
import { Avatar, Empty, Loading, Pill } from '../../components/primitives'
import {
  useChangeRole,
  useParticipants,
  useRemoveMember,
  useTeamMembers,
  useUnlockCommitment,
} from '../../hooks/queries'
import { formatDateTime } from '../../lib/format'
import type { TeamMember } from '../../lib/types'
import { useAuthContext } from '../../layouts/authContext'

export function AdminMembersPage() {
  const auth = useAuthContext()
  const members = useTeamMembers(auth.team?.id)
  const participants = useParticipants(auth.team?.id)
  const removeMember = useRemoveMember(auth.team?.id)
  const changeRole = useChangeRole(auth.team?.id)
  const unlock = useUnlockCommitment()
  const [removing, setRemoving] = useState<TeamMember | null>(null)
  const [unlocking, setUnlocking] = useState<{ userId: string; name: string; goalId: string } | null>(
    null,
  )
  const [error, setError] = useState('')

  if (members.isLoading) return <Loading />
  if (!members.data?.length) return <Empty title="No members" body="Invite someone first." />

  const admins = members.data.filter((member) => member.role === 'ADMIN').length
  const byUser = new Map(
    (participants.data ?? [])
      .filter((row) => row.challenge_id === auth.challenge_id)
      .map((row) => [row.user_id, row]),
  )

  return (
    <>
      {error && <p className="error">{error}</p>}
      <section className="card admin-section">
        <h2>Members</h2>
        <p className="hint">
          Removing someone ends their participation but keeps their history. The last admin cannot be
          removed or demoted.
        </p>
        {members.data.map((member) => {
          const participant = byUser.get(member.id)
          const isSelf = member.id === auth.user.id
          const lastAdmin = member.role === 'ADMIN' && admins === 1
          return (
            <div className="admin-row member-row" key={member.id}>
              <Avatar name={member.display_name} url={member.avatar_url} />
              <div className="grow">
                <b>
                  <Link to={`/team/members/${member.id}`}>{member.display_name}</Link>
                  {isSelf && ' (you)'}
                </b>
                <span>{member.email}</span>
                {participant && (
                  <small>
                    {participant.goals_committed_at
                      ? `Committed ${formatDateTime(participant.goals_committed_at)}`
                      : participant.goals_locked_at
                        ? `Locked ${formatDateTime(participant.goals_locked_at)} with ${participant.goals_committed} goals`
                        : `Due ${formatDateTime(participant.goals_due_at)} · ${participant.goals_committed} goals so far`}
                  </small>
                )}
              </div>
              <Pill tone={member.role === 'ADMIN' ? 'good' : undefined}>{member.role}</Pill>
              {participant && (
                <Pill tone={participant.goals_committed ? undefined : 'warn'}>
                  {participant.goals_committed} goals
                </Pill>
              )}
              <div className="row-actions">
                {!lastAdmin && (
                  <button
                    className="ghost small"
                    disabled={changeRole.isPending}
                    onClick={async () => {
                      setError('')
                      try {
                        await changeRole.mutateAsync({
                          userId: member.id,
                          role: member.role === 'ADMIN' ? 'MEMBER' : 'ADMIN',
                        })
                      } catch (reason) {
                        setError((reason as Error).message)
                      }
                    }}
                  >
                    <ShieldCheck /> {member.role === 'ADMIN' ? 'Demote' : 'Promote'}
                  </button>
                )}
                {participant?.goals_locked_at && participant.first_goal_id && (
                  <button
                    className="ghost small"
                    onClick={() =>
                      setUnlocking({
                        userId: member.id,
                        name: member.display_name,
                        goalId: participant.first_goal_id!,
                      })
                    }
                  >
                    <LockKeyholeOpen /> Unlock
                  </button>
                )}
                {!isSelf && !lastAdmin && (
                  <button className="ghost small danger-text" onClick={() => setRemoving(member)}>
                    <UserMinus /> Remove
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </section>

      {removing && (
        <ConfirmDialog
          title={`Remove ${removing.display_name}?`}
          body="They lose access to the team immediately. Their goals and check-ins stay on record, and they are excluded from the final forfeit calculation."
          confirmLabel="Remove member"
          pending={removeMember.isPending}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            setError('')
            try {
              await removeMember.mutateAsync(removing.id)
              setRemoving(null)
            } catch (reason) {
              setError((reason as Error).message)
              setRemoving(null)
            }
          }}
        />
      )}

      {unlocking && (
        <ConfirmDialog
          title={`Reopen ${unlocking.name}'s commitment?`}
          body="Their whole commitment unlocks for 24 hours so targets and structure can be corrected. This is recorded in the audit log against your name."
          confirmLabel="Unlock for 24 hours"
          pending={unlock.isPending}
          onCancel={() => setUnlocking(null)}
          onConfirm={async () => {
            setError('')
            try {
              await unlock.mutateAsync(unlocking.goalId)
              setUnlocking(null)
            } catch (reason) {
              setError((reason as Error).message)
              setUnlocking(null)
            }
          }}
        />
      )}
    </>
  )
}
