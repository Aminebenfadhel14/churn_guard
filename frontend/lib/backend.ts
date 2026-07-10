/**
 * Couche d'intégration avec le backend FastAPI de ChurnGuard.
 *
 * Ces fonctions appellent les vrais endpoints (/predict, /explain, /recommend,
 * /what-if). Elles sont conçues pour être utilisées **côté serveur** (Route
 * Handlers Next.js ou Server Components), afin que la clé API ne soit jamais
 * exposée au navigateur.
 *
 * Bascule mock / réel : voir `.env.local` et la fonction `useMock()`.
 * Tant que le backend n'est pas déployé, l'application utilise `lib/api.ts`
 * (données simulées). Une fois l'API en ligne, mettez CHURNGUARD_USE_MOCK=false
 * et branchez ces fonctions dans vos pages (en les rendant `async`).
 */

import type { Client } from './types'

const BASE_URL = process.env.CHURNGUARD_API_URL ?? 'http://127.0.0.1:8000'
const API_KEY = process.env.CHURNGUARD_API_KEY ?? ''

/** Indique si l'application doit utiliser les données mock plutôt que l'API. */
export function useMock(): boolean {
  // Par défaut on reste en mock tant que la variable n'est pas explicitement "false".
  return (process.env.NEXT_PUBLIC_USE_MOCK ?? 'true') !== 'false'
}

/** Réponses attendues du backend (à ajuster selon l'implémentation FastAPI). */
export interface PredictResponse {
  risk_score: number
  prediction: 0 | 1
  risk_level: 'faible' | 'moyen' | 'eleve'
}

export interface ExplainResponse {
  features: { feature: string; contribution: number; description?: string }[]
}

export interface RecommendResponse {
  recommendations: {
    action: string
    detail?: string
    impact: number
    priority: 'Haute' | 'Moyenne' | 'Basse'
  }[]
}

export interface WhatIfResponse {
  risk_score: number
  delta: number
}

/** Appel HTTP générique vers le backend, avec injection de la clé API. */
async function call<T>(path: string, body: unknown): Promise<T> {
  const reponse = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': API_KEY,
    },
    body: JSON.stringify(body),
    // On ne met pas en cache les prédictions (données par requête).
    cache: 'no-store',
  })
  if (!reponse.ok) {
    const texte = await reponse.text().catch(() => '')
    throw new Error(`API ChurnGuard ${path} → ${reponse.status} ${texte}`)
  }
  return (await reponse.json()) as T
}

export function apiPredict(client: Partial<Client>) {
  return call<PredictResponse>('/predict', client)
}

export function apiExplain(client: Partial<Client>) {
  return call<ExplainResponse>('/explain', { client })
}

export function apiRecommend(client: Partial<Client>, riskScore: number) {
  return call<RecommendResponse>('/recommend', { client, risk_score: riskScore })
}

export function apiWhatIf(
  client: Partial<Client>,
  overrides: Record<string, number | string>,
) {
  return call<WhatIfResponse>('/what-if', { client, overrides })
}
