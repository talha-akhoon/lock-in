/** Compare the running SPA build against /version.json after a deploy. */

export type AppVersion = { version: string }

export const RUNNING_VERSION: string = import.meta.env.VITE_APP_VERSION || 'dev'

export const VERSION_POLL_MS = 5 * 60 * 1000

export function isStaleVersion(running: string, remote: unknown): boolean {
  if (!remote || typeof remote !== 'object' || !('version' in remote)) return false
  const version = (remote as AppVersion).version
  return typeof version === 'string' && version.length > 0 && version !== running
}

export async function fetchRemoteVersion(): Promise<unknown> {
  const response = await fetch('/version.json', { cache: 'no-store' })
  if (!response.ok) throw new Error(`version.json returned ${response.status}`)
  return response.json()
}

export async function shouldPromptRefresh(running = RUNNING_VERSION): Promise<boolean> {
  try {
    return isStaleVersion(running, await fetchRemoteVersion())
  } catch {
    return false
  }
}
