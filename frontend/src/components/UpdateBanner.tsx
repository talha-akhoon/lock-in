import { RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { RUNNING_VERSION, shouldPromptRefresh, VERSION_POLL_MS } from '../lib/appVersion'

export function UpdateBanner({ runningVersion = RUNNING_VERSION }: { runningVersion?: string }) {
  const [stale, setStale] = useState(false)

  useEffect(() => {
    if (stale) return
    let cancelled = false

    async function check() {
      if (cancelled || document.visibilityState === 'hidden') return
      if (await shouldPromptRefresh(runningVersion)) {
        if (!cancelled) setStale(true)
      }
    }

    void check()
    const id = window.setInterval(check, VERSION_POLL_MS)
    function onResume() {
      void check()
    }
    document.addEventListener('visibilitychange', onResume)
    window.addEventListener('focus', onResume)
    return () => {
      cancelled = true
      window.clearInterval(id)
      document.removeEventListener('visibilitychange', onResume)
      window.removeEventListener('focus', onResume)
    }
  }, [runningVersion, stale])

  if (!stale) return null

  return (
    <div className="nudge update-banner" role="status">
      <RefreshCw />
      <div>
        <b>A new version of LockIn is ready</b>
        <span>Refresh to pick up the latest deploy. Unsaved check-in text will be lost.</span>
      </div>
      <button type="button" className="primary" onClick={() => window.location.reload()}>
        Refresh
      </button>
    </div>
  )
}
