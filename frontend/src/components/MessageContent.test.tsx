/* @vitest-environment jsdom */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MessageContent } from './MessageContent'

describe('MessageContent', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders plain text without markdown when markdown is off', () => {
    render(
      <MessageContent content="**[South China Morning Post](https://www.scmp.com/topics/narendra-modi)**: summary" />,
    )

    expect(
      screen.getByText(
        '**[South China Morning Post](https://www.scmp.com/topics/narendra-modi)**: summary',
      ),
    ).toBeTruthy()
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('renders bold markdown links as clickable anchors', () => {
    render(
      <MessageContent
        markdown
        content="**[South China Morning Post](https://www.scmp.com/topics/narendra-modi)**: This article discusses Modi's election victory."
      />,
    )

    const link = screen.getByRole('link', { name: 'South China Morning Post' })
    expect(link.getAttribute('href')).toBe('https://www.scmp.com/topics/narendra-modi')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    expect(link.closest('strong')).toBeTruthy()
    expect(screen.getByText(/This article discusses Modi's election victory/)).toBeTruthy()
    expect(screen.queryByText(/\*\*/)).toBeNull()
  })

  it('autolinks bare https URLs from citation-style replies', () => {
    render(<MessageContent markdown content="Source Name — https://example.com/article" />)

    const link = screen.getByRole('link', { name: 'https://example.com/article' })
    expect(link.getAttribute('href')).toBe('https://example.com/article')
  })

  it('blocks images and unsupported GFM elements while keeping surrounding text', () => {
    const { container } = render(
      <MessageContent
        markdown
        content={[
          'Before',
          '![logo](https://example.com/logo.png)',
          '| a | b |',
          '| - | - |',
          '| 1 | 2 |',
          '~~struck~~ and - [ ] task',
          'After',
        ].join('\n\n')}
      />,
    )

    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('table')).toBeNull()
    expect(container.querySelector('del')).toBeNull()
    expect(container.querySelector('input')).toBeNull()
    expect(screen.getByText(/Before/)).toBeTruthy()
    expect(screen.getByText(/After/)).toBeTruthy()
    expect(screen.getByText(/struck/)).toBeTruthy()
  })
})
