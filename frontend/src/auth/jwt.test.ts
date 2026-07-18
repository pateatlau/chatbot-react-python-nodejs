import { describe, expect, it } from 'vitest'
import { getJwtExpiryMs, isJwtExpired } from './jwt'

// Real JWTs use base64url with padding stripped (RFC 7515 Appendix C), not
// plain base64. Encode segments the same way so tests exercise the actual
// wire format instead of masking a padding bug.
function toBase64Url(value: string): string {
  return btoa(value).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function makeJwt(exp: number | undefined): string {
  const header = toBase64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const payload = toBase64Url(JSON.stringify(exp === undefined ? {} : { exp }))
  return `${header}.${payload}.signature`
}

describe('jwt expiry helpers', () => {
  it('returns null for a malformed token, and treats it as expired (fail closed)', () => {
    expect(getJwtExpiryMs('not-a-jwt')).toBeNull()
    expect(isJwtExpired('not-a-jwt')).toBe(true)
  })

  it('returns null when the payload has no exp claim, and treats it as expired (fail closed)', () => {
    const token = makeJwt(undefined)
    expect(getJwtExpiryMs(token)).toBeNull()
    expect(isJwtExpired(token)).toBe(true)
  })

  it('treats a non-numeric exp claim as expired (fail closed)', () => {
    const header = toBase64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    const payload = toBase64Url(JSON.stringify({ exp: 'not-a-number' }))
    const token = `${header}.${payload}.signature`

    expect(getJwtExpiryMs(token)).toBeNull()
    expect(isJwtExpired(token)).toBe(true)
  })

  it('reports a future exp as not expired', () => {
    const futureExpSeconds = Math.floor(Date.now() / 1000) + 3600
    const token = makeJwt(futureExpSeconds)

    expect(getJwtExpiryMs(token)).toBe(futureExpSeconds * 1000)
    expect(isJwtExpired(token)).toBe(false)
  })

  it('reports a past exp as expired', () => {
    const pastExpSeconds = Math.floor(Date.now() / 1000) - 3600
    const token = makeJwt(pastExpSeconds)

    expect(isJwtExpired(token)).toBe(true)
  })

  it('decodes a base64url payload with stripped padding', () => {
    // toBase64Url() always strips trailing '=' padding, matching real JWTs.
    // Pick an exp whose JSON length is not a multiple of 4 after encoding so
    // this specifically exercises the padding-restoration path.
    const futureExpSeconds = Math.floor(Date.now() / 1000) + 42
    const token = makeJwt(futureExpSeconds)

    expect(getJwtExpiryMs(token)).toBe(futureExpSeconds * 1000)
  })
})
