/* @vitest-environment jsdom */

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuthContext } from './AuthContext'
import { AuthApiError } from '../api/authClient'
import {
  getStoredAccessToken,
  getStoredGuestToken,
  getStoredUser,
  storeGuestToken,
  storeSession,
} from '../auth/tokenStorage'
import * as authClient from '../api/authClient'
import type { AuthenticatedUser, TokenResponse } from '../types/auth'

function createDeferred<T>(): {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
} {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const user: AuthenticatedUser = {
  id: 'user-1',
  email: 'person@example.com',
  display_name: 'Person',
  picture_url: null,
}

function makeJwt(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const exp = Math.floor(Date.now() / 1000) + expSecondsFromNow
  const payload = btoa(JSON.stringify({ exp }))
  return `${header}.${payload}.signature`
}

describe('AuthContext', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  it('starts as guest when no session is stored', () => {
    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    expect(result.current.status).toBe('guest')
    expect(result.current.user).toBeNull()
  })

  it('clears a dangling access token when the stored user is missing (partial/corrupt state)', () => {
    // Simulate a partial localStorage state (e.g. token written but the user
    // write failed/was cleared separately) without going through storeSession,
    // which always writes both.
    window.localStorage.setItem('auth.accessToken', 'orphaned-token')

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    expect(result.current.status).toBe('guest')
    expect(result.current.user).toBeNull()
    expect(getStoredAccessToken()).toBeNull()
  })

  it('clears a dangling stored user when the access token is missing (reverse partial/corrupt state)', () => {
    window.localStorage.setItem('auth.user', JSON.stringify(user))

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    expect(result.current.status).toBe('guest')
    expect(result.current.user).toBeNull()
    expect(getStoredUser()).toBeNull()
  })

  it('rehydrates an authenticated session from storage on mount', async () => {
    storeSession(makeJwt(3600), user)

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    await waitFor(() => {
      expect(result.current.status).toBe('authenticated')
    })
    expect(result.current.user).toEqual(user)
  })

  it('clears an expired stored session on mount and flags sessionExpired', () => {
    storeSession(makeJwt(-3600), user)

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    expect(result.current.status).toBe('guest')
    expect(result.current.user).toBeNull()
    expect(result.current.sessionExpired).toBe(true)
    expect(getStoredAccessToken()).toBeNull()
  })

  it('does not flag an unexpired stored session as expired', () => {
    storeSession(makeJwt(3600), user)

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    expect(result.current.status).toBe('authenticated')
    expect(result.current.sessionExpired).toBe(false)
  })

  it('treats a malformed stored token as expired (fail closed) rather than trusting it', () => {
    storeSession('not-a-real-jwt', user)

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    expect(result.current.status).toBe('guest')
    expect(result.current.user).toBeNull()
    expect(result.current.sessionExpired).toBe(true)
    expect(getStoredAccessToken()).toBeNull()
  })

  it('dismissSessionExpired clears the flag', () => {
    storeSession(makeJwt(-3600), user)
    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })
    expect(result.current.sessionExpired).toBe(true)

    act(() => {
      result.current.dismissSessionExpired()
    })

    expect(result.current.sessionExpired).toBe(false)
  })

  it('login exchanges the Google ID token and stores the resulting session', async () => {
    vi.spyOn(authClient, 'loginWithGoogle').mockResolvedValue({
      access_token: 'new-jwt',
      token_type: 'bearer',
      expires_in: 3600,
      user,
    })

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('google-id-token')
    })

    expect(result.current.status).toBe('authenticated')
    expect(result.current.user).toEqual(user)
    expect(getStoredAccessToken()).toBe('new-jwt')
    expect(getStoredUser()).toEqual(user)
  })

  it('logout clears the stored session and reverts to guest', async () => {
    storeSession(makeJwt(3600), user)
    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })
    await waitFor(() => expect(result.current.status).toBe('authenticated'))

    act(() => {
      result.current.logout()
    })

    expect(result.current.status).toBe('guest')
    expect(result.current.user).toBeNull()
    expect(getStoredAccessToken()).toBeNull()
  })

  it('login sends the stored guest token so the backend can link it', async () => {
    storeGuestToken('presenting-guest-token')
    const loginSpy = vi.spyOn(authClient, 'loginWithGoogle').mockResolvedValue({
      access_token: 'new-jwt',
      token_type: 'bearer',
      expires_in: 3600,
      user,
    })

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('google-id-token')
    })

    expect(loginSpy).toHaveBeenCalledWith('google-id-token', 'presenting-guest-token')
  })

  it('retains the guest token across login', async () => {
    storeGuestToken('presenting-guest-token')
    vi.spyOn(authClient, 'loginWithGoogle').mockResolvedValue({
      access_token: 'new-jwt',
      token_type: 'bearer',
      expires_in: 3600,
      user,
    })

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('google-id-token')
    })

    expect(getStoredGuestToken()).toBe('presenting-guest-token')
  })

  it('classifies auth_not_configured as a friendly, non-throwing loginError', async () => {
    vi.spyOn(authClient, 'loginWithGoogle').mockRejectedValue(
      new AuthApiError('boom', 503, 'auth_not_configured'),
    )

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('google-id-token')
    })

    expect(result.current.status).toBe('guest')
    expect(result.current.loginError).toEqual({
      code: 'auth_not_configured',
      message: 'Login is temporarily unavailable.',
    })
  })

  it('classifies invalid_google_token as a friendly loginError', async () => {
    vi.spyOn(authClient, 'loginWithGoogle').mockRejectedValue(
      new AuthApiError('boom', 401, 'invalid_google_token'),
    )

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('google-id-token')
    })

    expect(result.current.loginError).toEqual({
      code: 'invalid_google_token',
      message: 'Google sign-in failed. Please try again.',
    })
  })

  it('classifies a non-AuthApiError (network failure) as a generic loginError', async () => {
    vi.spyOn(authClient, 'loginWithGoogle').mockRejectedValue(new TypeError('Failed to fetch'))

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('google-id-token')
    })

    expect(result.current.loginError).toEqual({
      code: 'network_error',
      message: 'Could not reach the backend. Check your connection and try again.',
    })
  })

  it('clears loginError on the next login attempt', async () => {
    const loginSpy = vi
      .spyOn(authClient, 'loginWithGoogle')
      .mockRejectedValueOnce(new AuthApiError('boom', 401, 'invalid_google_token'))
      .mockResolvedValueOnce({
        access_token: 'new-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        user,
      })

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('bad-token')
    })
    expect(result.current.loginError).not.toBeNull()

    await act(async () => {
      await result.current.login('good-token')
    })

    expect(result.current.loginError).toBeNull()
    expect(result.current.status).toBe('authenticated')
    expect(loginSpy).toHaveBeenCalledTimes(2)
  })

  it('handleInvalidAccessToken clears the session and flags sessionExpired', async () => {
    storeSession(makeJwt(3600), user)
    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })
    await waitFor(() => expect(result.current.status).toBe('authenticated'))

    act(() => {
      result.current.handleInvalidAccessToken()
    })

    expect(result.current.status).toBe('guest')
    expect(result.current.user).toBeNull()
    expect(result.current.sessionExpired).toBe(true)
    expect(getStoredAccessToken()).toBeNull()
  })

  it('retains the guest token across logout', async () => {
    storeSession(makeJwt(3600), user)
    storeGuestToken('presenting-guest-token')
    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })
    await waitFor(() => expect(result.current.status).toBe('authenticated'))

    act(() => {
      result.current.logout()
    })

    expect(getStoredGuestToken()).toBe('presenting-guest-token')
  })

  it('ignores a login result that resolves after logout() already ran (stale attempt guard)', async () => {
    const deferred = createDeferred<TokenResponse>()
    vi.spyOn(authClient, 'loginWithGoogle').mockReturnValue(deferred.promise)

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    let loginPromise: Promise<void> = Promise.resolve()
    act(() => {
      loginPromise = result.current.login('google-id-token')
    })

    act(() => {
      result.current.logout()
    })
    expect(result.current.status).toBe('guest')

    await act(async () => {
      deferred.resolve({
        access_token: 'new-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        user,
      })
      await loginPromise
    })

    expect(result.current.status).toBe('guest')
    expect(result.current.user).toBeNull()
    expect(getStoredAccessToken()).toBeNull()
  })

  it('ignores a login result that resolves after handleInvalidAccessToken() already ran (stale attempt guard)', async () => {
    const deferred = createDeferred<TokenResponse>()
    vi.spyOn(authClient, 'loginWithGoogle').mockReturnValue(deferred.promise)

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    let loginPromise: Promise<void> = Promise.resolve()
    act(() => {
      loginPromise = result.current.login('google-id-token')
    })

    act(() => {
      result.current.handleInvalidAccessToken()
    })
    expect(result.current.sessionExpired).toBe(true)

    await act(async () => {
      deferred.resolve({
        access_token: 'new-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        user,
      })
      await loginPromise
    })

    // The stale login must not resurrect authenticated state nor clear the
    // sessionExpired prompt set by the newer handleInvalidAccessToken() call.
    expect(result.current.status).toBe('guest')
    expect(result.current.sessionExpired).toBe(true)
    expect(getStoredAccessToken()).toBeNull()
  })

  it('applies only the newer login result when two login() calls overlap and the older resolves last', async () => {
    const firstAttempt = createDeferred<TokenResponse>()
    const secondAttempt = createDeferred<TokenResponse>()
    vi.spyOn(authClient, 'loginWithGoogle')
      .mockReturnValueOnce(firstAttempt.promise)
      .mockReturnValueOnce(secondAttempt.promise)

    const { result } = renderHook(() => useAuthContext(), { wrapper: AuthProvider })

    let firstLoginPromise: Promise<void> = Promise.resolve()
    let secondLoginPromise: Promise<void> = Promise.resolve()
    act(() => {
      firstLoginPromise = result.current.login('first-id-token')
    })
    act(() => {
      secondLoginPromise = result.current.login('second-id-token')
    })

    const secondUser: AuthenticatedUser = { ...user, id: 'user-2', display_name: 'Second' }

    // The newer (second) call resolves first...
    await act(async () => {
      secondAttempt.resolve({
        access_token: 'second-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        user: secondUser,
      })
      await secondLoginPromise
    })
    expect(result.current.user).toEqual(secondUser)

    // ...and the stale (first) call resolving afterward must not overwrite it.
    await act(async () => {
      firstAttempt.resolve({
        access_token: 'first-jwt',
        token_type: 'bearer',
        expires_in: 3600,
        user,
      })
      await firstLoginPromise
    })

    expect(result.current.user).toEqual(secondUser)
    expect(getStoredAccessToken()).toBe('second-jwt')
  })
})
