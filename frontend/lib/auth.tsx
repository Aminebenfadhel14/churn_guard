'use client'

/**
 * Session utilisateur (login/logout) — mécanisme additif à la clé API
 * existante côté backend : ici on gère uniquement les sessions humaines du
 * frontend web (token JWT obtenu via /auth/login, stocké en localStorage).
 */

import { createContext, type ReactNode, useContext, useEffect, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000'
const TOKEN_KEY = 'churnguard_token'

export interface AuthUser {
  username: string
  nom_complet: string
  role: string
}

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

interface AuthValue {
  user: AuthUser | null
  status: AuthStatus
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  /** Appel fetch vers le backend, avec injection automatique du token de session. */
  apiFetch: (path: string, init?: RequestInit) => Promise<Response>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  useEffect(() => {
    const stocke = localStorage.getItem(TOKEN_KEY)
    if (!stocke) {
      setStatus('unauthenticated')
      return
    }
    fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${stocke}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((u: AuthUser) => {
        setUser(u)
        setToken(stocke)
        setStatus('authenticated')
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY)
        setStatus('unauthenticated')
      })
  }, [])

  const login = async (username: string, password: string) => {
    const rep = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const d = await rep.json().catch(() => ({}))
    if (!rep.ok) throw new Error(d.detail ?? "Impossible de se connecter.")
    localStorage.setItem(TOKEN_KEY, d.access_token)
    setToken(d.access_token)
    setUser(d.user)
    setStatus('authenticated')
  }

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
    setStatus('unauthenticated')
  }

  const apiFetch = (path: string, init: RequestInit = {}) =>
    fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        ...(init.headers ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })

  return (
    <AuthContext.Provider value={{ user, status, login, logout, apiFetch }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé sous AuthProvider')
  return ctx
}
