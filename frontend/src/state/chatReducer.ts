import type { Message } from '../types/chat'

export interface ChatState {
  messages: Message[]
  error: string | null
}

export const initialChatState: ChatState = {
  messages: [],
  error: null,
}

export type ChatAction =
  | { type: 'ADD_USER_MESSAGE'; message: Message }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SET_ERROR'; message: string }
  | { type: 'START_MESSAGE'; id: string; createdAt: string }
  | { type: 'APPEND_DELTA'; id: string; content: string }
  | { type: 'END_MESSAGE'; id: string }
  | { type: 'RETRY_MESSAGE'; id: string }
  | { type: 'STOP_MESSAGE'; id: string }
  | { type: 'INTERRUPT_MESSAGE'; id: string; message: string }
  | { type: 'STREAM_ERROR'; id: string; message: string; code?: string }

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'ADD_USER_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.message],
      }

    case 'CLEAR_ERROR':
      return {
        ...state,
        error: null,
      }

    case 'SET_ERROR':
      return {
        ...state,
        error: action.message,
      }

    case 'START_MESSAGE':
      return {
        ...state,
        error: null,
        messages: [
          ...state.messages,
          {
            id: action.id,
            role: 'assistant',
            content: '',
            status: 'streaming',
            createdAt: action.createdAt,
            canRetry: false,
          },
        ],
      }

    case 'APPEND_DELTA':
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? {
                ...message,
                content: message.content + action.content,
                errorMessage: undefined,
                errorCode: undefined,
                canRetry: false,
              }
            : message,
        ),
      }

    case 'END_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? {
                ...message,
                status: 'complete',
                errorMessage: undefined,
                errorCode: undefined,
                canRetry: false,
              }
            : message,
        ),
      }

    case 'RETRY_MESSAGE':
      return {
        ...state,
        error: null,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? {
                ...message,
                content: '',
                status: 'streaming',
                errorMessage: undefined,
                errorCode: undefined,
                canRetry: false,
              }
            : message,
        ),
      }

    case 'STOP_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? {
                ...message,
                status: 'stopped',
                errorMessage: undefined,
                errorCode: undefined,
                canRetry: false,
              }
            : message,
        ),
      }

    case 'INTERRUPT_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? {
                ...message,
                status: 'interrupted',
                errorMessage: action.message,
                canRetry: true,
              }
            : message,
        ),
      }

    case 'STREAM_ERROR':
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? {
                ...message,
                status: 'error',
                errorMessage: action.message,
                errorCode: action.code,
                canRetry: true,
              }
            : message,
        ),
      }

    default:
      return state
  }
}
