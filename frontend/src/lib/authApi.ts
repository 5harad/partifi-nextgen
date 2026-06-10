import type { AuthMeResponse } from '../types/auth'
import type { LibraryResponse } from '../types/library'
import { getCsrfToken } from './api'

async function authFetch(input: RequestInfo, init?: RequestInit): Promise<Response> {
  return fetch(input, { ...init, credentials: 'include' })
}

export async function fetchAuthMe(): Promise<AuthMeResponse> {
  const res = await authFetch('/api/v1/auth/me')
  if (!res.ok) throw new Error('Failed to fetch auth status')
  return res.json()
}

export async function googleLogin(accessToken: string): Promise<AuthMeResponse> {
  const res = await authFetch('/api/v1/auth/google', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ access_token: accessToken }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Google login failed')
  }
  return res.json()
}

export async function logout(): Promise<void> {
  const res = await authFetch('/api/v1/auth/logout', { method: 'POST' })
  if (!res.ok) throw new Error('Logout failed')
}

export async function fetchLibrary(): Promise<LibraryResponse> {
  const res = await authFetch('/api/v1/library')
  if (res.status === 401) {
    throw new Error('You must be logged in to view your library.')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load library')
  }
  return res.json()
}

export async function fetchFavoriteStatus(accessId: string): Promise<boolean> {
  const res = await authFetch(`/api/v1/library/favorites/${encodeURIComponent(accessId)}`)
  if (!res.ok) return false
  const data = await res.json()
  return Boolean(data.favorite)
}

export async function updateFavorite(
  accessId: string,
  action: 'add' | 'remove',
): Promise<boolean> {
  const csrf = await getCsrfToken()
  const res = await authFetch(`/api/v1/library/favorites/${encodeURIComponent(accessId)}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
    },
    body: JSON.stringify({ action }),
  })
  if (res.status === 401) {
    throw new Error('You must be logged in to save scores to your library.')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update library')
  }
  const data = await res.json()
  return Boolean(data.favorite)
}

export function getGoogleClientId(): string {
  return (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) ?? ''
}
