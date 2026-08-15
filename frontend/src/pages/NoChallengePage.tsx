import { CalendarRange } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Empty, PageHeader } from '../components/primitives'
import { useAuthContext } from '../layouts/authContext'

/** Rendered in place of the app when a team exists but no challenge does. */
export function NoChallengePage() {
  const auth = useAuthContext()
  const admin = auth.role === 'ADMIN'
  return (
    <>
      <PageHeader eyebrow={auth.team?.name ?? 'Your team'} title="No challenge yet" />
      <Empty
        title={admin ? 'Set the terms' : 'Waiting on your admin'}
        body={
          admin
            ? 'Nothing is running yet. Create the challenge and everyone in the team gets the same window and forfeit.'
            : 'Your admin has not created a challenge yet. Once they do, you will have a few days to set your goals.'
        }
      >
        {admin && (
          <Link className="primary" to="/onboarding/challenge">
            <CalendarRange /> Create the challenge
          </Link>
        )}
      </Empty>
    </>
  )
}
