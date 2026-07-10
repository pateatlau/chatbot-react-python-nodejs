import type { Message } from '../types/chat'
import { StreamingIndicator } from './StreamingIndicator'

interface MessageBubbleProps {
  message: Message
  onRetry?: (messageId: string) => void
}

export function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  const isWaitingForFirstToken = message.status === 'streaming' && message.content === ''
  const canRetry = message.canRetry && onRetry && message.role === 'assistant'

  return (
    <div
      className={`message-bubble message-bubble--${message.role} message-bubble--${message.status}`}
    >
      {isWaitingForFirstToken ? (
        <StreamingIndicator />
      ) : (
        <p className="message-bubble__content">{message.content}</p>
      )}
      {message.status === 'error' && (
        <p className="message-bubble__error">{message.errorMessage ?? 'Something went wrong.'}</p>
      )}
      {message.status === 'interrupted' && (
        <p className="message-bubble__error">
          {message.errorMessage ?? 'The stream was interrupted before completion.'}
        </p>
      )}
      {message.status === 'stopped' && <p className="message-bubble__stopped">Stopped.</p>}
      {canRetry ? (
        <button type="button" className="message-bubble__retry" onClick={() => onRetry(message.id)}>
          Retry
        </button>
      ) : null}
    </div>
  )
}
