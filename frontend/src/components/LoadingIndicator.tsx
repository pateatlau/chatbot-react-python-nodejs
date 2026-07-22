export type LoadingIndicatorVariant = 'inline' | 'skeleton' | 'overlay'

interface LoadingIndicatorProps {
  label?: string
  variant?: LoadingIndicatorVariant
  className?: string
}

interface LoadingSpinnerProps {
  className?: string
}

/** Shared spinning indicator used by inline/overlay variants and upload buttons. */
export function LoadingSpinner({ className = 'h-4 w-4' }: LoadingSpinnerProps) {
  return (
    <span
      className={[
        'inline-block animate-spin rounded-full border-2 border-shell-400 border-t-brand-600',
        className,
      ].join(' ')}
      aria-hidden="true"
    />
  )
}

/** Three-dot pulse used by in-bubble streaming states (typing, search, RAG). */
export function TypingDots() {
  return (
    <span className="inline-flex gap-1" aria-hidden="true">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-shell-400" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-shell-400 [animation-delay:120ms]" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-shell-400 [animation-delay:240ms]" />
    </span>
  )
}

export function LoadingIndicator({ label, variant = 'inline', className }: LoadingIndicatorProps) {
  if (variant === 'skeleton') {
    return (
      <div
        className={['rounded-chat border border-zinc-300 bg-zinc-100 p-3', className]
          .filter(Boolean)
          .join(' ')}
        role="status"
        aria-live="polite"
        aria-label={label ?? 'Loading'}
      >
        <div className="h-3 w-24 animate-pulse rounded bg-zinc-300" aria-hidden="true" />
        <div className="mt-2 h-3 w-full animate-pulse rounded bg-zinc-200" aria-hidden="true" />
        {label ? <span className="sr-only">{label}</span> : null}
      </div>
    )
  }

  if (variant === 'overlay') {
    return (
      <div
        className={[
          'flex min-h-[8rem] flex-col items-center justify-center gap-3 text-sm text-shell-700',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
        role="status"
        aria-live="polite"
        aria-label={label ?? 'Loading'}
      >
        <LoadingSpinner className="h-6 w-6" />
        {label ? <span>{label}</span> : null}
      </div>
    )
  }

  return (
    <div
      className={['inline-flex items-center gap-2 text-sm text-shell-700', className]
        .filter(Boolean)
        .join(' ')}
      role="status"
      aria-live="polite"
      aria-label={label ?? 'Loading'}
    >
      <LoadingSpinner />
      {label ? <span>{label}</span> : null}
    </div>
  )
}
