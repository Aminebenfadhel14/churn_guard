export type RiskLevel = 'faible' | 'moyen' | 'eleve'

export interface Client {
  id: string
  name: string
  email: string
  company: string
  region: string
  segment: string
  tenureMonths: number
  monthlyCharges: number
  totalSpend: number
  contract: 'Mensuel' | 'Annuel' | 'Bi-annuel'
  products: number
  supportTickets: number
  lastInteractionDays: number
  satisfaction: number
  riskScore: number // 0-100
}

export interface ShapFeature {
  feature: string
  label: string
  contribution: number // signed, positive = augmente le risque
  description: string
}

export interface Recommendation {
  id: string
  action: string
  detail: string
  impact: number // estimated risk reduction in points
  priority: 'Haute' | 'Moyenne' | 'Basse'
}

export interface WhatIfVariable {
  key: string
  label: string
  min: number
  max: number
  step: number
  value: number
  unit?: string
}

export interface DashboardStats {
  totalClients: number
  atRiskCount: number
  atRiskPct: number
  avgChurnRate: number
  avgRiskScore: number
}

export interface TrendPoint {
  month: string
  churnRate: number
  clients: number
}

export interface RiskBucket {
  level: string
  count: number
  fill: string
}

export interface ScatterPoint {
  tenure: number
  risk: number
  name: string
}
