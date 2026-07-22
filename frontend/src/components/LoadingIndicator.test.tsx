/* @vitest-environment jsdom */

import { cleanup, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { LoadingIndicator } from './LoadingIndicator'
import { renderWithProviders } from '../test/renderWithProviders'

describe('LoadingIndicator', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders label and spinner for inline variant', () => {
    renderWithProviders(<LoadingIndicator variant="inline" label="Loading conversation…" />)

    expect(screen.getByRole('status', { name: /loading conversation/i })).toBeTruthy()
    expect(screen.getByText('Loading conversation…')).toBeTruthy()
    expect(document.querySelector('[aria-hidden="true"].animate-spin')).toBeTruthy()
  })

  it('renders skeleton variant with accessible status', () => {
    renderWithProviders(
      <LoadingIndicator variant="skeleton" label="Loading saved conversations…" />,
    )

    expect(screen.getByRole('status', { name: /loading saved conversations/i })).toBeTruthy()
  })

  it('renders overlay variant with label and spinner', () => {
    renderWithProviders(<LoadingIndicator variant="overlay" label="Loading workspace…" />)

    expect(screen.getByRole('status', { name: /loading workspace/i })).toBeTruthy()
    expect(screen.getByText('Loading workspace…')).toBeTruthy()
  })

  it('uses aria-live polite on status regions', () => {
    renderWithProviders(<LoadingIndicator variant="inline" label="Loading documents…" />)

    expect(
      screen.getByRole('status', { name: /loading documents/i }).getAttribute('aria-live'),
    ).toBe('polite')
  })
})
