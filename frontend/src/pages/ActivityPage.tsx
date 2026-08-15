import { Link } from 'react-router-dom'
import { Avatar, Empty, ErrorState, Loading, PageHeader } from '../components/primitives'
import { useActivity, useChallenge } from '../hooks/queries'
import { formatAmount, relativeTime } from '../lib/format'
import type { ActivityEntry } from '../lib/types'

function summarise(item: ActivityEntry): string {
  const unit = item.unit ? ` ${item.unit}` : ''
  if (item.completed === true) return `completed ${item.goal_title}`
  if (item.completed === false) return `reopened ${item.goal_title}`
  if (item.manual_percentage !== null)
    return `moved ${item.goal_title} to ${item.manual_percentage}%`
  if (item.numeric_delta !== null) {
    const sign = Number(item.numeric_delta) >= 0 ? '+' : ''
    return `logged ${sign}${formatAmount(item.numeric_delta)}${unit} on ${item.goal_title}`
  }
  if (item.numeric_value !== null)
    return `updated ${item.goal_title} to ${formatAmount(item.numeric_value)}${unit}`
  return `checked in on ${item.goal_title}`
}

export function ActivityPage() {
  const challenge = useChallenge()
  const feed = useActivity(challenge.data?.id)

  if (challenge.isLoading || feed.isLoading) return <Loading label="Loading activity" />
  if (feed.isError) return <ErrorState body={(feed.error as Error).message} />

  return (
    <>
      <PageHeader
        eyebrow="Team momentum"
        title="Activity"
        description="Every update is proof that someone showed up."
      />
      {!feed.data?.length ? (
        <Empty
          title="The feed is quiet"
          body="Progress updates from your team will appear here as everyone checks in."
        />
      ) : (
        <section className="people-list card">
          {feed.data.map((item) => (
            <div className="activity-item" key={item.id}>
              <Avatar name={item.display_name} url={item.avatar_url} />
              <div>
                <b>
                  <Link to={`/team/members/${item.user_id}`}>{item.display_name}</Link>
                </b>
                <span>{summarise(item)}</span>
                {item.note && <p>{item.note}</p>}
              </div>
              <time title={item.created_at}>{relativeTime(item.created_at)}</time>
            </div>
          ))}
        </section>
      )}
    </>
  )
}
