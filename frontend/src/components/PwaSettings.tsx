import { BellRing, Download, Smartphone } from 'lucide-react'
import { useEffect, useState } from 'react'
import { usePushConfig } from '../hooks/queries'
import {
  disablePush,
  enablePush,
  hasPushSubscription,
  isIosDevice,
  isStandalone,
  pushSupported,
} from '../lib/push'

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function PwaSettings() {
  const config = usePushConfig()
  const [subscribed, setSubscribed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null)
  const [installed, setInstalled] = useState(isStandalone())

  useEffect(() => {
    let cancelled = false
    hasPushSubscription()
      .then((value) => {
        if (!cancelled) setSubscribed(value)
      })
      .catch(() => {
        if (!cancelled) setSubscribed(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    function onPrompt(event: Event) {
      event.preventDefault()
      setInstallEvent(event as BeforeInstallPromptEvent)
    }
    function onInstalled() {
      setInstalled(true)
      setInstallEvent(null)
    }
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  async function togglePush() {
    if (!config.data?.public_key) return
    setBusy(true)
    setError('')
    try {
      if (subscribed) {
        await disablePush()
        setSubscribed(false)
      } else {
        await enablePush(config.data.public_key)
        setSubscribed(true)
      }
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function install() {
    if (!installEvent) return
    await installEvent.prompt()
    const choice = await installEvent.userChoice
    if (choice.outcome === 'accepted') setInstalled(true)
    setInstallEvent(null)
  }

  const canPush = pushSupported() && config.data?.enabled
  const ios = isIosDevice()

  return (
    <section className="card admin-section">
      <h2>
        <Smartphone /> On this device
      </h2>
      <p className="hint">
        Install LockIn and turn on push so every time a teammate logs progress or finishes a goal
        it reaches you when the tab is closed. Private goal titles are never included. On iPhone,
        add LockIn to the Home Screen first — Safari only delivers push to an installed app.
      </p>

      <div className="admin-row">
        <b>Install app</b>
        {installed ? (
          <span>Installed</span>
        ) : installEvent ? (
          <button className="ghost small" onClick={install}>
            <Download /> Install LockIn
          </button>
        ) : ios && !installed ? (
          <span>Share → Add to Home Screen</span>
        ) : (
          <span>Use the browser install prompt when it appears</span>
        )}
      </div>

      <div className="admin-row">
        <b>Push notifications</b>
        {!canPush ? (
          <span>Not available in this browser</span>
        ) : (
          <button className="ghost small" onClick={togglePush} disabled={busy || config.isLoading}>
            <BellRing />
            {busy ? 'Working…' : subscribed ? 'Turn off' : 'Turn on'}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
