/* @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MessageList } from './MessageList'
import { renderWithProviders } from '../test/renderWithProviders'

describe('MessageList empty transcript', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis.HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    })
  })

  afterEach(() => {
    cleanup()
  })

  it('shows welcome copy for all users', () => {
    renderWithProviders(<MessageList messages={[]} />)

    expect(screen.getByRole('heading', { name: 'Start the conversation' })).toBeTruthy()
    expect(
      screen.getByText(
        'Ask a question, iterate on an idea, or test a prompt to see streaming responses here.',
      ),
    ).toBeTruthy()
  })

  it('shows toggle hints for authenticated users when tools or RAG are enabled', () => {
    renderWithProviders(<MessageList messages={[]} isAuthenticated toolsEnabled ragEnabled />)

    expect(screen.getByText('Turn on Web search for live results.')).toBeTruthy()
    expect(screen.getByText('Turn on Documents to ground answers in your uploads.')).toBeTruthy()
  })

  it('shows only enabled toggle hints for authenticated users', () => {
    renderWithProviders(
      <MessageList messages={[]} isAuthenticated toolsEnabled ragEnabled={false} />,
    )

    expect(screen.getByText('Turn on Web search for live results.')).toBeTruthy()
    expect(screen.queryByText('Turn on Documents to ground answers in your uploads.')).toBeNull()
  })

  it('omits toggle hints for guests even when server flags are on', () => {
    render(<MessageList messages={[]} isAuthenticated={false} toolsEnabled ragEnabled />)

    expect(screen.queryByText('Turn on Web search for live results.')).toBeNull()
    expect(screen.queryByText('Turn on Documents to ground answers in your uploads.')).toBeNull()
  })
})
