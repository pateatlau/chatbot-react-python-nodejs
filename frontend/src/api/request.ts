import { getStoredAccessToken } from '../auth/tokenStorage'

/** Empty string uses same-origin `/api` (Vite dev proxy). Override for production builds. */
function resolveApiBaseUrl(): string {
  const configured = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()
  if (configured) {
    return configured.replace(/\/$/, '')
  }
  return ''
}

export const API_BASE_URL: string = resolveApiBaseUrl()

export const REQUEST_ID_HEADER = 'X-Request-ID'

let lastRequestId: string | null = null
let pendingRetryRequestId: string | null = null

export function setRetryRequestId(requestId: string | null): void {
  pendingRetryRequestId = requestId
}

export function getLastRequestId(): string | null {
  return lastRequestId
}

export function captureRequestId(response: Response): void {
  lastRequestId = response.headers.get(REQUEST_ID_HEADER)
}

interface ErrorResponse {
  error?: {
    code?: string
    message?: string
  }
}

/** Vite dev proxy returns 502 when backend-python is not listening on :8000. */
export function backendUnavailableMessage(status: number): string | null {
  if (status === 502 || status === 503 || status === 504) {
    return 'Cannot reach the backend. From the repo root run: make backend'
  }
  return null
}

export async function parseErrorEnvelope(
  response: Response,
  fallbackMessage: string,
): Promise<{ message: string; status: number; code?: string }> {
  const proxyMessage = backendUnavailableMessage(response.status)
  if (proxyMessage) {
    return { message: proxyMessage, status: response.status }
  }

  let payload: ErrorResponse | null

  try {
    payload = (await response.json()) as ErrorResponse
  } catch {
    payload = null
  }

  return {
    message: payload?.error?.message ?? fallbackMessage,
    status: response.status,
    code: payload?.error?.code,
  }
}

/** Builds auth headers for document/RAG endpoints (Bearer JWT + optional retry request id). */
export function buildAuthHeaders(options?: { json?: boolean }): Record<string, string> {
  const headers: Record<string, string> = {}
  if (options?.json !== false) {
    headers['Content-Type'] = 'application/json'
  }
  const accessToken = getStoredAccessToken()
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }
  if (pendingRetryRequestId) {
    headers[REQUEST_ID_HEADER] = pendingRetryRequestId
    pendingRetryRequestId = null
  }
  return headers
}
