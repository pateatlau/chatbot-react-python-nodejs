import { describe, expect, it } from 'vitest'
import { backendUnavailableMessage, parseErrorEnvelope } from './request'

describe('backendUnavailableMessage', () => {
  it('maps proxy gateway errors to backend startup guidance', () => {
    expect(backendUnavailableMessage(502)).toMatch(/make backend/)
    expect(backendUnavailableMessage(503)).toMatch(/make backend/)
    expect(backendUnavailableMessage(504)).toMatch(/make backend/)
  })

  it('returns null for other status codes', () => {
    expect(backendUnavailableMessage(401)).toBeNull()
    expect(backendUnavailableMessage(500)).toBeNull()
  })
})

describe('parseErrorEnvelope', () => {
  it('returns backend guidance for Vite proxy 502 without parsing JSON', async () => {
    const result = await parseErrorEnvelope(
      new Response(null, { status: 502 }),
      'Stream request failed: 502',
    )

    expect(result.message).toMatch(/cannot reach the backend/i)
    expect(result.status).toBe(502)
  })
})
