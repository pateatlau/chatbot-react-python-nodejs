/* @vitest-environment jsdom */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearAccessToken,
  getStoredAccessToken,
  getStoredGuestToken,
  getStoredUser,
  storeGuestToken,
  storeSession,
} from './tokenStorage'
import type { AuthenticatedUser } from '../types/auth'

const user: AuthenticatedUser = {
  id: 'user-1',
  email: 'person@example.com',
  display_name: 'Person',
  picture_url: null,
}

describe('tokenStorage', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    window.localStorage.clear()
  })

  it('returns null when nothing is stored', () => {
    expect(getStoredAccessToken()).toBeNull()
    expect(getStoredUser()).toBeNull()
  })

  it('round-trips the access token and user through storeSession', () => {
    storeSession('jwt-token', user)

    expect(getStoredAccessToken()).toBe('jwt-token')
    expect(getStoredUser()).toEqual(user)
  })

  it('clears both the token and the user on clearAccessToken', () => {
    storeSession('jwt-token', user)
    clearAccessToken()

    expect(getStoredAccessToken()).toBeNull()
    expect(getStoredUser()).toBeNull()
  })

  it('rolls back the access token if the user write fails, keeping storage atomic', () => {
    // vi.spyOn on jsdom's localStorage.setItem is unreliable (jsdom
    // implements Storage via a Proxy), so use a small fake Storage we fully
    // control instead: the 2nd setItem call (USER_KEY) throws, simulating a
    // failure partway through storeSession's two writes.
    const backing = new Map<string, string>()
    let setItemCalls = 0
    const fakeStorage: Storage = {
      getItem: (key: string) => backing.get(key) ?? null,
      setItem: (key: string, value: string) => {
        setItemCalls += 1
        if (setItemCalls === 2) {
          throw new Error('QuotaExceededError')
        }
        backing.set(key, value)
      },
      removeItem: (key: string) => {
        backing.delete(key)
      },
      clear: () => backing.clear(),
      key: (index: number) => Array.from(backing.keys())[index] ?? null,
      get length() {
        return backing.size
      },
    }
    vi.stubGlobal('localStorage', fakeStorage)

    storeSession('jwt-token', user)

    expect(getStoredAccessToken()).toBeNull()
    expect(getStoredUser()).toBeNull()

    vi.unstubAllGlobals()
  })

  it('round-trips the guest token through storeGuestToken', () => {
    expect(getStoredGuestToken()).toBeNull()

    storeGuestToken('guest-token-1')

    expect(getStoredGuestToken()).toBe('guest-token-1')
  })

  it('retains the guest token across clearAccessToken (plan Section 4.3)', () => {
    storeSession('jwt-token', user)
    storeGuestToken('guest-token-1')

    clearAccessToken()

    expect(getStoredAccessToken()).toBeNull()
    expect(getStoredGuestToken()).toBe('guest-token-1')
  })
})
