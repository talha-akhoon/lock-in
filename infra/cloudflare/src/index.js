/**
 * Reverse proxy from the custom domain to Cloud Run.
 *
 * Cloud Run's built-in domain mapping is not available in every region, and a
 * Worker on the free plan costs nothing. `ORIGIN_HOST` is set in wrangler.toml.
 */

/** Hop-by-hop and Cloudflare-injected headers that must not be forwarded. */
const STRIPPED_REQUEST_HEADERS = ['host', 'cf-connecting-ip', 'cf-ray', 'cf-visitor']

export default {
  async fetch(request, env) {
    const origin = env.ORIGIN_HOST
    if (!origin) {
      return new Response('ORIGIN_HOST is not configured', { status: 500 })
    }

    const url = new URL(request.url)
    url.protocol = 'https:'
    url.hostname = origin
    url.port = ''

    const headers = new Headers(request.headers)
    for (const name of STRIPPED_REQUEST_HEADERS) headers.delete(name)
    // Cloud Run runs behind --proxy-headers, so the app trusts these for
    // scheme and client IP.
    headers.set('X-Forwarded-Host', new URL(request.url).host)
    headers.set('X-Forwarded-Proto', 'https')

    const upstream = new Request(url, {
      method: request.method,
      headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
      redirect: 'manual',
    })

    const response = await fetch(upstream)

    // Rewrite redirects that point back at the run.app host so the browser
    // stays on the custom domain and keeps sending its host-only cookies.
    const location = response.headers.get('location')
    if (location) {
      try {
        const target = new URL(location, url)
        if (target.hostname === origin) {
          target.hostname = new URL(request.url).hostname
          const rewritten = new Headers(response.headers)
          rewritten.set('location', target.toString())
          return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: rewritten,
          })
        }
      } catch {
        // A relative or malformed Location needs no rewriting.
      }
    }

    return response
  },
}
