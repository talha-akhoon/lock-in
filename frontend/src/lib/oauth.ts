/** Only the LockIn OAuth authorize path — never an open redirect. */
export function safeOAuthNext(raw: string | null | undefined): string | null {
  if (!raw) return null
  const path = raw.split('?')[0].split('#')[0]
  if (path !== '/oauth/authorize') return null
  if (raw.startsWith('//')) return null
  return raw
}
