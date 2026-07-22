'use client'

/**
 * Session utilisateur (login/logout) — mécanisme additif à la clé API
 * existante côté backend : ici on gère uniquement les sessions humaines du
 * frontend web (token JWT obtenu via /auth/login, stocké en localStorage).
 */

import { createContext, type ReactNode, useContext, useEffect, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000'
const TOKEN_KEY = 'churnguard_token'
/** Présent uniquement pendant une session "connecté en tant que" : le token
 * de l'admin d'origine, pour pouvoir y revenir sans se reconnecter. */
const TOKEN_ORIGINE_KEY = 'churnguard_original_token'

export interface AuthUser {
  username: string
  email: string | null
  nom_complet: string
  role: string
}

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

/** Résultat de `login` : soit la session est ouverte, soit un code de
 * vérification a été envoyé par email et il faut appeler `verifyOtp`. */
type ResultatLogin = { otpRequired: false } | { otpRequired: true; challengeToken: string; emailMasque: string }

interface AuthValue {
  user: AuthUser | null
  status: AuthStatus
  login: (username: string, password: string) => Promise<ResultatLogin>
  /** Échange un code de vérification reçu par email contre une session. */
  verifyOtp: (challengeToken: string, code: string) => Promise<void>
  /** Redemande l'envoi d'un code de vérification (délai anti-spam côté serveur). */
  resendOtp: (challengeToken: string) => Promise<void>
  /** Inscription libre-service : crée une organisation + son premier compte admin. */
  signup: (
    organisationNom: string,
    username: string,
    email: string,
    password: string,
    nomComplet: string,
  ) => Promise<void>
  logout: () => void
  /** Recharge l'utilisateur courant (après une modification de son propre compte). */
  refreshMe: () => Promise<void>
  /** Vrai si la session actuelle est un "se connecter en tant que" (admin -> employé). */
  impersonating: boolean
  /** Ouvre une session sur le compte de cet employé (admin uniquement, sans mot de passe). */
  impersonate: (username: string) => Promise<void>
  /** Revient à la session admin d'origine. */
  stopImpersonating: () => Promise<void>
  /** Appel fetch vers le backend, avec injection automatique du token de session. */
  apiFetch: (path: string, init?: RequestInit) => Promise<Response>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [impersonating, setImpersonating] = useState(false)

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
        setImpersonating(!!localStorage.getItem(TOKEN_ORIGINE_KEY))
        setStatus('authenticated')
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(TOKEN_ORIGINE_KEY)
        setStatus('unauthenticated')
      })
  }, [])

  const ouvrirSession = (d: { access_token: string; user: AuthUser }) => {
    localStorage.setItem(TOKEN_KEY, d.access_token)
    setToken(d.access_token)
    setUser(d.user)
    setStatus('authenticated')
  }

  const login = async (username: string, password: string): Promise<ResultatLogin> => {
    const rep = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const d = await rep.json().catch(() => ({}))
    if (!rep.ok) throw new Error(d.detail ?? "Impossible de se connecter.")
    if (d.otp_required) {
      return { otpRequired: true, challengeToken: d.challenge_token, emailMasque: d.email_masque }
    }
    ouvrirSession(d)
    return { otpRequired: false }
  }

  const verifyOtp = async (challengeToken: string, code: string) => {
    const rep = await fetch(`${API_URL}/auth/login/verify-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ challenge_token: challengeToken, code }),
    })
    const d = await rep.json().catch(() => ({}))
    if (!rep.ok) throw new Error(d.detail ?? 'Code de vérification invalide.')
    ouvrirSession(d)
  }

  const resendOtp = async (challengeToken: string) => {
    const rep = await fetch(`${API_URL}/auth/login/resend-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ challenge_token: challengeToken }),
    })
    const d = await rep.json().catch(() => ({}))
    if (!rep.ok) throw new Error(d.detail ?? "Impossible de renvoyer le code.")
  }

  const signup = async (
    organisationNom: string,
    username: string,
    email: string,
    password: string,
    nomComplet: string,
  ) => {
    const rep = await fetch(`${API_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        organisation_nom: organisationNom,
        username,
        email,
        password,
        nom_complet: nomComplet,
      }),
    })
    const d = await rep.json().catch(() => ({}))
    if (!rep.ok) throw new Error(d.detail ?? 'Impossible de créer le compte.')
    ouvrirSession(d)
  }

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(TOKEN_ORIGINE_KEY)
    setToken(null)
    setUser(null)
    setImpersonating(false)
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

  const refreshMe = async () => {
    const rep = await apiFetch('/auth/me')
    if (rep.ok) setUser(await rep.json())
  }

  const impersonate = async (username: string) => {
    const rep = await apiFetch(`/auth/users/${encodeURIComponent(username)}/impersonate`, {
      method: 'POST',
    })
    const d = await rep.json().catch(() => ({}))
    if (!rep.ok) throw new Error(d.detail ?? 'Impossible de se connecter à ce compte.')
    // Ne conserve l'admin d'origine que s'il n'y en a pas déjà un (pas de
    // double-impersonation qui écraserait la vraie session admin).
    if (!localStorage.getItem(TOKEN_ORIGINE_KEY) && token) {
      localStorage.setItem(TOKEN_ORIGINE_KEY, token)
    }
    ouvrirSession(d)
    setImpersonating(true)
  }

  const stopImpersonating = async () => {
    const origine = localStorage.getItem(TOKEN_ORIGINE_KEY)
    if (!origine) return
    localStorage.removeItem(TOKEN_ORIGINE_KEY)
    const rep = await fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${origine}` } })
    if (!rep.ok) {
      logout()
      return
    }
    const u: AuthUser = await rep.json()
    localStorage.setItem(TOKEN_KEY, origine)
    setToken(origine)
    setUser(u)
    setImpersonating(false)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        status,
        login,
        verifyOtp,
        resendOtp,
        signup,
        logout,
        refreshMe,
        impersonating,
        impersonate,
        stopImpersonating,
        apiFetch,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé sous AuthProvider')
  return ctx
}
