import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthContext } from '../context/AuthContext'
import { LoadingIndicator } from './LoadingIndicator'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuthContext()

  if (status === 'loading') {
    return (
      <div className="min-h-dvh bg-shell-100 px-4 py-12">
        <LoadingIndicator variant="inline" label="Checking sign-in…" />
      </div>
    )
  }

  if (status === 'authenticated') {
    return <>{children}</>
  }

  // Guest or locally detected expired session — send to public chat surface.
  return <Navigate to="/" replace />
}
