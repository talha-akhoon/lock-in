import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Avatar, Empty, Loading, PageHeader, Pill } from '../components/primitives'
import { useTeamMembers } from '../hooks/queries'
import { formatDate } from '../lib/format'
import { useAuthContext } from '../layouts/authContext'

export function TeamPage() {
  const auth = useAuthContext()
  const members = useTeamMembers(auth.team?.id)

  if (members.isLoading) return <Loading label="Loading the team" />

  return (
    <>
      <PageHeader
        eyebrow="Your accountability circle"
        title={auth.team?.name ?? 'Team'}
        description="The people who know exactly what you said you would do."
      />
      {!members.data?.length ? (
        <Empty title="Nobody else yet" body="Invite the people who will hold you to this." />
      ) : (
        <div className="people-list card">
          {members.data.map((member) => (
            <Link to={`/team/members/${member.id}`} key={member.id}>
              <Avatar name={member.display_name} url={member.avatar_url} />
              <div>
                <b>
                  {member.display_name}
                  {member.id === auth.user.id && ' (you)'}
                </b>
                <span>Joined {formatDate(member.joined_at)}</span>
              </div>
              <Pill tone={member.role === 'ADMIN' ? 'good' : undefined}>{member.role}</Pill>
              <ChevronRight />
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
