/* @vitest-environment jsdom */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const GIS_SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

async function freshModule() {
  vi.resetModules()
  return await import('./googleIdentityLoader')
}

function setGoogleGlobal(): void {
  window.google = {
    accounts: {
      id: {
        initialize: () => {},
        renderButton: () => {},
        disableAutoSelect: () => {},
      },
    },
  }
}

function clearGoogleGlobal(): void {
  delete window.google
}

function getInjectedScript(): HTMLScriptElement {
  const script = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SCRIPT_SRC}"]`)
  if (!script) {
    throw new Error('Expected loadGoogleIdentityScript to inject a script tag.')
  }
  return script
}

describe('loadGoogleIdentityScript', () => {
  beforeEach(() => {
    document.head.innerHTML = ''
    clearGoogleGlobal()
  })

  afterEach(() => {
    document.head.innerHTML = ''
    clearGoogleGlobal()
  })

  it('resolves immediately when window.google.accounts.id already exists', async () => {
    setGoogleGlobal()
    const { loadGoogleIdentityScript } = await freshModule()

    await expect(loadGoogleIdentityScript()).resolves.toBeUndefined()
  })

  it('resolves once the script loads and window.google.accounts.id becomes available', async () => {
    const { loadGoogleIdentityScript } = await freshModule()

    const promise = loadGoogleIdentityScript()
    setGoogleGlobal()
    getInjectedScript().dispatchEvent(new Event('load'))

    await expect(promise).resolves.toBeUndefined()
  })

  it('rejects (and allows retry) when the script loads but window.google never initializes', async () => {
    const { loadGoogleIdentityScript } = await freshModule()

    const firstAttempt = loadGoogleIdentityScript()
    getInjectedScript().dispatchEvent(new Event('load'))

    await expect(firstAttempt).rejects.toThrow('did not initialize')

    // A caller retrying after the rejection should get a fresh attempt, not
    // a promise permanently stuck reporting "ready".
    setGoogleGlobal()
    const secondAttempt = loadGoogleIdentityScript()
    getInjectedScript().dispatchEvent(new Event('load'))

    await expect(secondAttempt).resolves.toBeUndefined()
  })

  it('rejects (and allows retry) on a script load error', async () => {
    const { loadGoogleIdentityScript } = await freshModule()

    const firstAttempt = loadGoogleIdentityScript()
    getInjectedScript().dispatchEvent(new Event('error'))

    await expect(firstAttempt).rejects.toThrow('Failed to load')

    setGoogleGlobal()
    const secondAttempt = loadGoogleIdentityScript()
    getInjectedScript().dispatchEvent(new Event('load'))

    await expect(secondAttempt).resolves.toBeUndefined()
  })
})
