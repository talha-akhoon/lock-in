/** Thin fetch wrapper: session cookies, CSRF echo, and structured errors. */

export class ApiError extends Error {
  readonly status: number
  /** Backend error code such as GOALS_LOCKED or ALREADY_IN_TEAM, when present. */
  readonly code: string | null

  constructor(message: string, status: number, code: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const CSRF_COOKIE = 'lockin_csrf'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((item) => item.startsWith(`${name}=`))
    ?.split('=')[1]
}

type ErrorBody = {
  detail?: string | { code?: string; message?: string } | Array<{ msg?: string }>
}

function describe(body: ErrorBody, status: number): ApiError {
  const detail = body.detail
  if (typeof detail === 'string') return new ApiError(detail, status)
  if (Array.isArray(detail)) {
    // FastAPI validation errors arrive as a list of per-field problems.
    const first = detail[0]?.msg ?? 'Request failed validation'
    return new ApiError(first, status)
  }
  if (detail && typeof detail === 'object') {
    return new ApiError(detail.message ?? 'Request failed', status, detail.code ?? null)
  }
  return new ApiError(`Request failed (${status})`, status)
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (!SAFE_METHODS.has(method)) {
    const csrf = readCookie(CSRF_COOKIE)
    if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf))
  }

  const response = await fetch(`/api/v1${path}`, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorBody
    throw describe(body, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return api<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
}

export function put<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'PUT', body: JSON.stringify(body) })
}

export function del(path: string): Promise<void> {
  return api<void>(path, { method: 'DELETE' })
}
