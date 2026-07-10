import { CLIENTS, riskLevel } from './mock-data'
import type {
  Client,
  DashboardStats,
  Recommendation,
  ScatterPoint,
  ShapFeature,
  TrendPoint,
  WhatIfVariable,
} from './types'

/**
 * Mock API layer for ChurnGuard.
 *
 * These functions currently return mocked data derived from `mock-data.ts`.
 * When the FastAPI backend is ready, swap the bodies for `fetch()` calls to
 * the corresponding endpoints (/predict, /explain, /recommend, /what-if)
 * using `process.env.CHURNGUARD_API_URL` and `process.env.CHURNGUARD_API_KEY`.
 */

export function getClients(): Client[] {
  return CLIENTS
}

export function getClient(id: string): Client | undefined {
  return CLIENTS.find((c) => c.id === id)
}

export function getDashboardStats(): DashboardStats {
  const total = CLIENTS.length
  const atRisk = CLIENTS.filter((c) => riskLevel(c.riskScore) === 'eleve').length
  const avgRisk =
    CLIENTS.reduce((sum, c) => sum + c.riskScore, 0) / Math.max(1, total)
  // Modeled average churn rate: share of clients predicted to churn (score > 50)
  const churners = CLIENTS.filter((c) => c.riskScore > 50).length
  return {
    totalClients: total,
    atRiskCount: atRisk,
    atRiskPct: Math.round((atRisk / total) * 1000) / 10,
    avgChurnRate: Math.round((churners / total) * 1000) / 10,
    avgRiskScore: Math.round(avgRisk * 10) / 10,
  }
}

export function getRiskDistribution() {
  const buckets = { faible: 0, moyen: 0, eleve: 0 }
  for (const c of CLIENTS) buckets[riskLevel(c.riskScore)]++
  return [
    { level: 'Faible', count: buckets.faible, key: 'faible' },
    { level: 'Moyen', count: buckets.moyen, key: 'moyen' },
    { level: 'Élevé', count: buckets.eleve, key: 'eleve' },
  ]
}

export function getChurnTrend(): TrendPoint[] {
  const months = [
    'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
    'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc',
  ]
  const base = [8.9, 9.4, 9.1, 10.2, 10.8, 11.3, 10.6, 11.9, 12.4, 12.1, 13.0, 13.6]
  return months.map((month, i) => ({
    month,
    churnRate: base[i],
    clients: 1180 + i * 12 + (i % 3) * 8,
  }))
}

export function getTenureScatter(): ScatterPoint[] {
  return CLIENTS.map((c) => ({
    tenure: c.tenureMonths,
    risk: c.riskScore,
    name: c.name,
  }))
}

export function getTopRiskClients(limit = 10): Client[] {
  return [...CLIENTS].sort((a, b) => b.riskScore - a.riskScore).slice(0, limit)
}

// --- /explain : SHAP contributions -----------------------------------------
export function explainClient(client: Client): ShapFeature[] {
  const features: ShapFeature[] = [
    {
      feature: 'contract',
      label: 'Type de contrat',
      contribution:
        client.contract === 'Mensuel' ? 22 : client.contract === 'Annuel' ? -6 : -14,
      description:
        client.contract === 'Mensuel'
          ? 'Contrat mensuel : le client peut partir à tout moment.'
          : 'Engagement long terme : le client est plus fidèle.',
    },
    {
      feature: 'satisfaction',
      label: 'Score de satisfaction',
      contribution: Math.round((7 - client.satisfaction) * 4 - 6),
      description: `Satisfaction déclarée de ${client.satisfaction}/6. Une satisfaction basse pousse au départ.`,
    },
    {
      feature: 'support_tickets',
      label: 'Tickets support (90j)',
      contribution: Math.round(client.supportTickets * 2.4 - 6),
      description: `${client.supportTickets} tickets ouverts récemment. Beaucoup de tickets = frustration.`,
    },
    {
      feature: 'tenure',
      label: 'Ancienneté',
      contribution: Math.round(Math.max(0, 24 - client.tenureMonths) * 1.1 - 8),
      description: `${client.tenureMonths} mois d'ancienneté. Les clients récents sont plus volatils.`,
    },
    {
      feature: 'last_interaction',
      label: 'Dernière interaction',
      contribution: Math.round(Math.max(0, client.lastInteractionDays - 30) * 0.35 - 4),
      description: `Dernière activité il y a ${client.lastInteractionDays} jours. L'inactivité est un signal fort.`,
    },
    {
      feature: 'products',
      label: 'Produits souscrits',
      contribution: Math.round((4 - client.products) * 3 - 3),
      description: `${client.products} produit(s). Moins de produits = client moins ancré.`,
    },
  ]
  return features
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 5)
}

// --- /recommend ------------------------------------------------------------
export function recommendClient(client: Client): Recommendation[] {
  const recs: Recommendation[] = []
  if (client.contract === 'Mensuel') {
    recs.push({
      id: 'r-contract',
      action: 'Proposer une offre annuelle avec remise',
      detail: 'Convertir le contrat mensuel en engagement annuel (-15%).',
      impact: 18,
      priority: 'Haute',
    })
  }
  if (client.satisfaction <= 3) {
    recs.push({
      id: 'r-csm',
      action: 'Appel de suivi par un Customer Success Manager',
      detail: 'Prise de contact personnalisée pour résoudre les irritants.',
      impact: 14,
      priority: 'Haute',
    })
  }
  if (client.supportTickets >= 5) {
    recs.push({
      id: 'r-support',
      action: 'Escalade prioritaire des tickets ouverts',
      detail: 'Assigner un référent technique dédié pour clôturer les incidents.',
      impact: 11,
      priority: 'Moyenne',
    })
  }
  if (client.lastInteractionDays > 45) {
    recs.push({
      id: 'r-reengage',
      action: 'Campagne de ré-engagement',
      detail: 'Séquence e-mail + démo des fonctionnalités non utilisées.',
      impact: 9,
      priority: 'Moyenne',
    })
  }
  if (client.products < 3) {
    recs.push({
      id: 'r-crosssell',
      action: 'Cross-sell d\'un module complémentaire',
      detail: 'Augmenter l\'ancrage produit avec une offre pertinente.',
      impact: 7,
      priority: 'Basse',
    })
  }
  if (recs.length === 0) {
    recs.push({
      id: 'r-monitor',
      action: 'Maintenir le suivi standard',
      detail: 'Client sain — surveiller les signaux faibles trimestriellement.',
      impact: 3,
      priority: 'Basse',
    })
  }
  return recs
}

// --- /what-if : variables & re-scoring -------------------------------------
export function whatIfVariables(client: Client): WhatIfVariable[] {
  return [
    {
      key: 'satisfaction',
      label: 'Score de satisfaction',
      min: 1,
      max: 6,
      step: 1,
      value: client.satisfaction,
      unit: '/6',
    },
    {
      key: 'supportTickets',
      label: 'Tickets support',
      min: 0,
      max: 15,
      step: 1,
      value: client.supportTickets,
    },
    {
      key: 'lastInteractionDays',
      label: 'Jours depuis interaction',
      min: 0,
      max: 120,
      step: 1,
      value: client.lastInteractionDays,
      unit: 'j',
    },
    {
      key: 'products',
      label: 'Produits souscrits',
      min: 1,
      max: 6,
      step: 1,
      value: client.products,
    },
  ]
}

const CONTRACT_ADJ: Record<Client['contract'], number> = {
  Mensuel: 22,
  Annuel: -6,
  'Bi-annuel': -14,
}

export function simulateScore(
  client: Client,
  overrides: {
    satisfaction: number
    supportTickets: number
    lastInteractionDays: number
    products: number
    contract: Client['contract']
  },
): number {
  let score = 32
  score += Math.max(0, 24 - client.tenureMonths) * 1.1
  score += CONTRACT_ADJ[overrides.contract]
  score += overrides.supportTickets * 2.4
  score += Math.max(0, overrides.lastInteractionDays - 30) * 0.35
  score += (7 - overrides.satisfaction) * 4
  score += (4 - overrides.products) * 3
  if (client.monthlyCharges > 120) score += 6
  return Math.round(Math.min(98, Math.max(3, score)))
}
