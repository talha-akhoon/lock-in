/**
 * Reverse proxy from the custom domain to Cloud Run.
 *
 * Cloud Run's built-in domain mapping is not available in every region, and a
 * Worker on the free plan costs nothing. `ORIGIN_HOST` is set in wrangler.toml.
 *
 * Hashed Vite files under /assets/ are cached at the edge so crawlers and
 * repeat visits do not wake Cloud Run for every JS/CSS byte.
 */

/** Hop-by-hop and Cloudflare-injected headers that must not be forwarded. */
const STRIPPED_REQUEST_HEADERS = ['host', 'cf-connecting-ip', 'cf-ray', 'cf-visitor']

function isHashedAsset(url, method) {
  return method === 'GET' && url.pathname.startsWith('/assets/')
}

export default {
  async fetch(request, env, ctx) {
    const origin = env.ORIGIN_HOST
    if (!origin) {
      return new Response('ORIGIN_HOST is not configured', { status: 500 })
    }

    const url = new URL(request.url)
    const cacheable = isHashedAsset(url, request.method)
    if (cacheable) {
      const hit = await caches.default.match(request)
      if (hit) return hit
    }

    url.protocol = 'https:'
    url.hostname = origin
    url.port = ''

    const headers = new Headers(request.headers)
    for (const name of STRIPPED_REQUEST_HEADERS) headers.delete(name)
    const clientIp = request.headers.get('CF-Connecting-IP')
    if (clientIp) headers.set('X-Forwarded-For', clientIp)
    // Cloud Run runs behind --proxy-headers, so the app trusts these for
    // scheme and client IP. X-Forwarded-Host is also the gate that lets the
    // origin distinguish this Worker from crawlers hitting *.run.app directly.
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

    if (cacheable && response.ok) {
      const cachedHeaders = new Headers(response.headers)
      cachedHeaders.set('Cache-Control', 'public, max-age=31536000, immutable')
      const cached = new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: cachedHeaders,
      })
      ctx.waitUntil(caches.default.put(request, cached.clone()))
      return cached
    }

    return response
  },
}
