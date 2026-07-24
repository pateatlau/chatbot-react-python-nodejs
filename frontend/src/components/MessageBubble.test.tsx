/* @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Message } from '../types/chat'
import { MessageBubble } from './MessageBubble'

function assistantMessage(content: string): Message {
  return {
    id: 'a1',
    role: 'assistant',
    content,
    status: 'complete',
    createdAt: '2026-07-24T00:00:00.000Z',
  }
}

function userMessage(content: string): Message {
  return {
    id: 'u1',
    role: 'user',
    content,
    status: 'complete',
    createdAt: '2026-07-24T00:00:00.000Z',
  }
}

describe('MessageBubble markdown', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders assistant markdown links and bold without raw asterisks', () => {
    render(
      <MessageBubble
        message={assistantMessage(
          '**[South China Morning Post](https://www.scmp.com/topics/narendra-modi)**: summary',
        )}
      />,
    )

    const link = screen.getByRole('link', { name: 'South China Morning Post' })
    expect(link.getAttribute('href')).toBe('https://www.scmp.com/topics/narendra-modi')
    expect(screen.queryByText(/\*\*/)).toBeNull()
  })

  it('keeps user messages as plain text', () => {
    render(
      <MessageBubble
        message={userMessage(
          '**[South China Morning Post](https://www.scmp.com/topics/narendra-modi)**',
        )}
      />,
    )

    expect(
      screen.getByText('**[South China Morning Post](https://www.scmp.com/topics/narendra-modi)**'),
    ).toBeTruthy()
    expect(screen.queryByRole('link')).toBeNull()
  })
})
