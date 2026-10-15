import { Center, Loader } from '@mantine/core'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from './AuthContext'
import type { PermissionRequirement } from '../registry/contract'

interface ProtectedRouteProps {
  children: ReactNode
  permission?: PermissionRequirement
}

export function ProtectedRoute({ children, permission }: ProtectedRouteProps) {
  const { user, loading, hasAnyPermission } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (permission && !hasAnyPermission(permission)) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
