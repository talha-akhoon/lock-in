import { BellOff } from 'lucide-react'
import {
  useNotificationPreferences,
  useUpdateNotificationPreferences,
} from '../hooks/queries'
import type { NotificationPreferenceType, NotificationType } from '../lib/types'
import { Loading } from './primitives'

export function NotificationSettings() {
  const prefs = useNotificationPreferences()
  const update = useUpdateNotificationPreferences()

  if (prefs.isLoading || !prefs.data) {
    return <Loading label="Loading notification settings" />
  }

  const muted = new Set(prefs.data.muted_types)
  const groups = groupTypes(prefs.data.types)

  function toggle(type: NotificationType, enabled: boolean) {
    const next = new Set(muted)
    if (enabled) next.delete(type)
    else next.add(type)
    update.mutate([...next])
  }

  return (
    <section className="card admin-section">
      <h2>
        <BellOff /> Notification types
      </h2>
      <p className="hint">
        Off means no bell and no push for that event. Turn a type back on any time. Joining the
        team is in-app only.
      </p>
      {groups.map((group) => (
        <div key={group.name} className="mute-group">
          <h3>{group.name}</h3>
          {group.types.map((item) => (
            <label className="admin-row mute-row" key={item.type}>
              <span>
                <b>{item.label}</b>
                <small>{item.description}</small>
              </span>
              <input
                type="checkbox"
                checked={!muted.has(item.type)}
                disabled={update.isPending}
                onChange={(event) => toggle(item.type, event.target.checked)}
                aria-label={item.label}
              />
            </label>
          ))}
        </div>
      ))}
    </section>
  )
}

function groupTypes(types: NotificationPreferenceType[]) {
  const groups: { name: string; types: NotificationPreferenceType[] }[] = []
  for (const item of types) {
    const last = groups[groups.length - 1]
    if (last && last.name === item.group) last.types.push(item)
    else groups.push({ name: item.group, types: [item] })
  }
  return groups
}
