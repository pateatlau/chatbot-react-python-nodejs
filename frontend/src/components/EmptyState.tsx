export interface EmptyStateAction {
  label: string
  onClick: () => void
  disabled?: boolean
}

export interface EmptyStateProps {
  title: string
  description: string
  action?: EmptyStateAction
  className?: string
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={[
        'rounded-chat border border-dashed border-zinc-300 bg-zinc-100/80 p-3 sm:p-4',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <h3 className="text-sm font-medium text-zinc-900">{title}</h3>
      <p className="mt-1 text-xs text-zinc-600 sm:text-sm">{description}</p>
      {action ? (
        <button
          type="button"
          className="mt-3 cursor-pointer rounded-chat bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-chat-card transition hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-200 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={action.onClick}
          disabled={action.disabled}
        >
          {action.label}
        </button>
      ) : null}
    </div>
  )
}
