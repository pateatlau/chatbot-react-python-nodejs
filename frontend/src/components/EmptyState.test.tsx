/* @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders title and description', () => {
    render(
      <EmptyState title="No documents yet" description="Upload a file above to get started." />,
    )

    expect(screen.getByRole('heading', { name: 'No documents yet' })).toBeTruthy()
    expect(screen.getByText('Upload a file above to get started.')).toBeTruthy()
  })

  it('renders action button and fires onClick', async () => {
    const onClick = vi.fn()
    render(
      <EmptyState
        title="No saved conversations yet"
        description="Start a new chat to build up your conversation history."
        action={{ label: 'New chat', onClick }}
      />,
    )

    const button = screen.getByRole('button', { name: 'New chat' })
    expect(button).toBeTruthy()
    await userEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('omits action button when action is not provided', () => {
    render(
      <EmptyState
        title="No saved conversations yet"
        description="Sign in to keep multiple conversations and pick up where you left off."
      />,
    )

    expect(screen.queryByRole('button')).toBeNull()
  })

  it('disables action button when action.disabled is true', () => {
    render(
      <EmptyState
        title="No saved conversations yet"
        description="Start a new chat to build up your conversation history."
        action={{ label: 'New chat', onClick: vi.fn(), disabled: true }}
      />,
    )

    expect(screen.getByRole('button', { name: 'New chat' })).toHaveProperty('disabled', true)
  })
})
