import { Bell, CheckCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from '../hooks/queries'
import { relativeTime } from '../lib/format'
import type { Notification } from '../lib/types'
import { Loading } from './primitives'

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const feed = useNotifications()
  const markRead = useMarkNotificationRead()
  const markAll = useMarkAllNotificationsRead()
  const navigate = useNavigate()
  const container = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClick(event: MouseEvent) {
      if (!container.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const unread = feed.data?.unread_count ?? 0

  function activate(notification: Notification) {
    if (!notification.read_at) markRead.mutate(notification.id)
    if (notification.link_path) {
      setOpen(false)
      navigate(notification.link_path)
    }
  }

  return (
    <div className="notification-wrap" ref={container}>
      <button
        className="icon-button"
        onClick={() => setOpen((value) => !value)}
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
      >
        <Bell />
        {unread > 0 && <span className="badge">{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open && (
        <div className="notification-panel card" role="dialog" aria-label="Notifications">
          <header>
            <div>
              <span className="eyebrow">Notifications</span>
              <h3>{unread > 0 ? `${unread} unread` : 'All caught up'}</h3>
            </div>
            {unread > 0 && (
              <button className="ghost small" onClick={() => markAll.mutate()}>
                <CheckCheck /> Mark all read
              </button>
            )}
          </header>
          {feed.isLoading ? (
            <Loading label="Loading notifications" />
          ) : !feed.data?.notifications.length ? (
            <p className="notification-empty">
              Nothing yet. Deadlines, milestones and teammate wins land here.
            </p>
          ) : (
            <ul>
              {feed.data.notifications.map((notification) => (
                <li key={notification.id} className={notification.read_at ? '' : 'unread'}>
                  <button onClick={() => activate(notification)}>
                    <b>{notification.title}</b>
                    {notification.body && <span>{notification.body}</span>}
                    <time>{relativeTime(notification.created_at)}</time>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
