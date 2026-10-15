import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import * as authApi from '../api/auth'
import { tokenStorage } from '../api/client'
import type { User } from '../api/types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  isAdmin: boolean
  hasPermission: (permission: string) => boolean
  hasAnyPermission: (requirement: string | string[]) => boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    if (!tokenStorage.access()) {
      setUser(null)
      return
    }
    try {
      setUser(await authApi.fetchMe())
    } catch {
      tokenStorage.clear()
      setUser(null)
    }
  }, [])

  useEffect(() => {
    void refreshUser().finally(() => setLoading(false))
  }, [refreshUser])

  useEffect(() => {
    const handleForcedLogout = () => setUser(null)
    window.addEventListener('bco:logout', handleForcedLogout)
    return () => window.removeEventListener('bco:logout', handleForcedLogout)
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await authApi.login({ email, password })
    setUser(response.user)
  }, [])

  const signOut = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      setUser(null)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAdmin: Boolean(user?.is_superuser || user?.permissions.includes('core.users.manage')),
      hasPermission: (permission: string) =>
        Boolean(user?.is_superuser || user?.permissions.includes(permission)),
      hasAnyPermission: (requirement: string | string[]) => {
        const codes = Array.isArray(requirement) ? requirement : [requirement]
        return Boolean(
          user?.is_superuser || codes.some((code) => user?.permissions.includes(code)),
        )
      },
      signIn,
      signOut,
      refreshUser,
    }),
    [user, loading, signIn, signOut, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
