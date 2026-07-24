import type { Components } from 'react-markdown'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'

interface MessageContentProps {
  content: string
  /** Render CommonMark/GFM (bold, links, lists). User messages stay plain text. */
  markdown?: boolean
}

/** Elements with custom handlers, plus soft-break `<br>` from remark-breaks. */
const ALLOWED_MARKDOWN_ELEMENTS = [
  'a',
  'p',
  'strong',
  'em',
  'ul',
  'ol',
  'li',
  'code',
  'pre',
  'br',
] as const

const markdownComponents: Components = {
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-brand-600 underline decoration-brand-500/40 underline-offset-2 transition hover:text-brand-500 hover:decoration-brand-500"
    >
      {children}
    </a>
  ),
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-shell-950">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="leading-7">{children}</li>,
  code: ({ children, className }) => {
    const isBlock = Boolean(className)
    if (isBlock) {
      return <code className={className}>{children}</code>
    }
    return (
      <code className="rounded bg-zinc-200/80 px-1 py-0.5 font-mono text-[0.85em] text-shell-900">
        {children}
      </code>
    )
  },
  pre: ({ children }) => (
    <pre className="mb-3 overflow-x-auto rounded-xl bg-zinc-900 px-3 py-2 font-mono text-xs leading-6 text-zinc-100 last:mb-0">
      {children}
    </pre>
  ),
}

export function MessageContent({ content, markdown = false }: MessageContentProps) {
  if (!markdown) {
    return (
      <p className="text-sm leading-7 whitespace-pre-wrap [overflow-wrap:anywhere]">{content}</p>
    )
  }

  return (
    <div className="text-sm leading-7 [overflow-wrap:anywhere]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={markdownComponents}
        allowedElements={[...ALLOWED_MARKDOWN_ELEMENTS]}
        unwrapDisallowed
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
