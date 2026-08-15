import { CircleUserRound, Target, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

export function Progress({ value, tone }: { value: number; tone?: 'muted' }) {
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <div
      className={tone === 'muted' ? 'progress muted' : 'progress'}
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span style={{ width: `${clamped}%` }} />
    </div>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string
  title: string
  description?: string
  children?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children}
    </header>
  )
}

export function Empty({
  title,
  body,
  children,
}: {
  title: string
  body: string
  children?: ReactNode
}) {
  return (
    <section className="empty card">
      <div>
        <Target />
      </div>
      <h2>{title}</h2>
      <p>{body}</p>
      {children}
    </section>
  )
}

export function ErrorState({
  title = 'Something went wrong',
  body,
  children,
}: {
  title?: string
  body: string
  children?: ReactNode
}) {
  return (
    <section className="empty card error-state" role="alert">
      <div>
        <TriangleAlert />
      </div>
      <h2>{title}</h2>
      <p>{body}</p>
      {children}
    </section>
  )
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span />
      <span />
      <span />
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function Avatar({
  name,
  url,
  size,
}: {
  name: string
  url?: string | null
  size?: 'lg'
}) {
  return (
    <div className={size === 'lg' ? 'avatar lg' : 'avatar'} aria-hidden="true">
      {url ? <img src={url} alt="" /> : name ? name[0].toUpperCase() : <CircleUserRound />}
    </div>
  )
}

export function Pill({
  children,
  tone,
}: {
  children: ReactNode
  tone?: 'good' | 'bad' | 'warn'
}) {
  return <span className={tone ? `pill ${tone}` : 'pill'}>{children}</span>
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <small className="field-error">{message}</small>
}
