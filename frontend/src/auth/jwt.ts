/**
 * Best-effort, unverified decode of a JWT's `exp` claim for local expiry
 * *awareness* only (plan Section 3.3's optional lightweight improvement,
 * promoted to load-bearing here since the backend intentionally never
 * returns a hard error for an expired app JWT — it silently degrades the
 * caller to guest instead). This is never used to establish trust; the
 * backend remains the sole authority on token validity.
 */

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split('.')
  if (parts.length !== 3) {
    return null
  }

  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
    const json = atob(padded)
    return JSON.parse(json) as Record<string, unknown>
  } catch {
    return null
  }
}

export function getJwtExpiryMs(token: string): number | null {
  const payload = decodeJwtPayload(token)
  const exp = payload?.exp
  return typeof exp === 'number' ? exp * 1000 : null
}

export function isJwtExpired(token: string): boolean {
  const expiryMs = getJwtExpiryMs(token)
  // Fail closed: a malformed token or a payload with a missing/non-numeric
  // `exp` can't be confirmed unexpired, so treat it as expired rather than
  // silently trusting it (this only ever affects local UX advisory state —
  // the backend independently re-validates the token on every request).
  if (expiryMs === null) {
    return true
  }
  return expiryMs <= Date.now()
}
