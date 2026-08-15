import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import type { AuthContext } from '../layouts/authContext'
import type { AuthMe } from '../lib/types'

export type RouteHandler =
  | unknown
  | ((request: { body: unknown; url: string }) => unknown)

export type RecordedRequest = { method: string; path: string; body: unknown }

export type FetchMock = {
  requests: RecordedRequest[]
  /** Requests for one route, e.g. `sent('POST /me/checkins')`. */
  sent(route: string): RecordedRequest[]
}

class HttpError {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    this.status = status
    this.detail = detail
  }
}

/** Lets a handler reply with a failure the same way the API would. */
export function httpError(status: number, detail: unknown): HttpError {
  return new HttpError(status, detail)
}

/**
 * Installs a fetch stub that routes on `METHOD /path` (path relative to
 * /api/v1). Exercising the real `api()` wrapper keeps CSRF and error decoding
 * under test rather than mocked away.
 */
export function mockFetch(routes: Record<string, RouteHandler>): FetchMock {
  const requests: RecordedRequest[] = []

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input)
      const path = url.replace('/api/v1', '')
      const method = (init.method ?? 'GET').toUpperCase()
      const body = init.body ? JSON.parse(String(init.body)) : null
      requests.push({ method, path, body })

      const key = `${method} ${path}`
      if (!(key in routes)) {
        return new Response(JSON.stringify({ detail: `No stub for ${key}` }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      const handler = routes[key]
      const value = typeof handler === 'function' ? handler({ body, url }) : handler
      if (value instanceof HttpError) {
        return new Response(JSON.stringify({ detail: value.detail }), {
          status: value.status,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (value === undefined) return new Response(null, { status: 204 })
      return new Response(JSON.stringify(value), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )

  return {
    requests,
    sent: (route) => {
      const [method, path] = route.split(' ')
      return requests.filter(
        (request) => request.method === method && request.path === path,
      )
    },
  }
}

function Providers({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

export function renderWithProviders(
  ui: ReactElement,
  { route = '/' }: { route?: string } = {},
): RenderResult {
  return render(
    <Providers>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </Providers>,
  )
}

/** Renders a page that expects auth from its parent route's outlet context. */
export function renderWithAuth(
  ui: ReactElement,
  auth: AuthMe,
  { route = '/', path = '/' }: { route?: string; path?: string } = {},
): RenderResult {
  return render(
    <Providers>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<Outlet context={{ auth } satisfies AuthContext} />}>
            <Route path={path} element={ui} />
          </Route>
        </Routes>
      </MemoryRouter>
    </Providers>,
  )
}

/** Renders arbitrary routes so redirects can be asserted on. */
export function renderRoutes(routes: ReactNode, route: string): RenderResult {
  return render(
    <Providers>
      <MemoryRouter initialEntries={[route]}>
        <Routes>{routes}</Routes>
      </MemoryRouter>
    </Providers>,
  )
}
