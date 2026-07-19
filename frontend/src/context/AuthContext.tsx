import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  devLogin,
  fetchAuthMe,
  getGoogleClientId,
  googleLoginWithCode,
  logout as apiLogout,
} from '../lib/authApi'
import type { AuthUser } from '../types/auth'

type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  googleEnabled: boolean
  refresh: () => Promise<void>
  loginWithGoogleCode: (code: string, redirectUri: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const googleEnabled = Boolean(getGoogleClientId())

  const refresh = useCallback(async () => {
    const data = await fetchAuthMe()
    setUser(data.user)
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        let data = await fetchAuthMe()
        // Local Vite previews use the populated Sharad account without requiring Google OAuth.
        if (import.meta.env.DEV && !data.user) {
          data = await devLogin()
        }
        if (!cancelled) setUser(data.user)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const loginWithGoogleCode = useCallback(async (code: string, redirectUri: string) => {
    const data = await googleLoginWithCode(code, redirectUri)
    setUser(data.user)
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setUser(null)
    navigate('/')
  }, [navigate])

  const value = useMemo(
    () => ({
      user,
      loading,
      googleEnabled,
      refresh,
      loginWithGoogleCode,
      logout,
    }),
    [user, loading, googleEnabled, refresh, loginWithGoogleCode, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
