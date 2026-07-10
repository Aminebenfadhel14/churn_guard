import type { Client, RiskLevel } from './types'

// --- Deterministic PRNG so data is stable between server & client renders ---
function mulberry32(seed: number) {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const FIRST_NAMES = [
  'Camille', 'Lucas', 'Emma', 'Hugo', 'Léa', 'Nathan', 'Chloé', 'Louis',
  'Manon', 'Gabriel', 'Sarah', 'Jules', 'Inès', 'Adam', 'Jade', 'Raphaël',
  'Alice', 'Paul', 'Louise', 'Arthur', 'Zoé', 'Théo', 'Lina', 'Noah',
  'Anna', 'Ethan', 'Rose', 'Sacha', 'Julie', 'Maxime',
]
const LAST_NAMES = [
  'Martin', 'Bernard', 'Dubois', 'Thomas', 'Robert', 'Petit', 'Durand',
  'Leroy', 'Moreau', 'Simon', 'Laurent', 'Lefebvre', 'Michel', 'Garcia',
  'David', 'Bertrand', 'Roux', 'Vincent', 'Fournier', 'Girard', 'Mercier',
  'Blanc', 'Guerin', 'Boyer', 'Garnier', 'Chevalier', 'Francois', 'Legrand',
]
const COMPANIES = [
  'Nexora', 'Lumina SA', 'Groupe Averon', 'Cortex Digital', 'Belmont & Cie',
  'Volta Energy', 'Meridian', 'Solstice', 'Altair Group', 'Kairos',
  'Novalink', 'Orbite', 'Pergame', 'Silva Retail', 'Onyx Finance',
  'Delta Logistique', 'Verdi Media', 'Helios', 'Cascade', 'Pyxis',
]
const REGIONS = [
  'Île-de-France', 'Auvergne-Rhône-Alpes', 'Nouvelle-Aquitaine', 'Occitanie',
  'Hauts-de-France', 'Grand Est', 'Provence-Alpes-Côte d\'Azur', 'Bretagne',
]
const SEGMENTS = ['Entreprise', 'PME', 'Startup', 'Grand compte']
const CONTRACTS: Client['contract'][] = ['Mensuel', 'Annuel', 'Bi-annuel']

function slug(v: string) {
  return v
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z]/gi, '')
    .toLowerCase()
}

function computeRisk(c: Omit<Client, 'riskScore' | 'id'>, rand: number) {
  let score = 32
  // Short tenure increases risk
  score += Math.max(0, 24 - c.tenureMonths) * 1.1
  // Month-to-month contracts are risky
  if (c.contract === 'Mensuel') score += 22
  else if (c.contract === 'Annuel') score -= 6
  else score -= 14
  // Support tickets
  score += c.supportTickets * 2.4
  // Inactivity
  score += Math.max(0, c.lastInteractionDays - 30) * 0.35
  // Low satisfaction
  score += (7 - c.satisfaction) * 4
  // Fewer products = less sticky
  score += (4 - c.products) * 3
  // High charges relative to value
  if (c.monthlyCharges > 120) score += 6
  score += (rand - 0.5) * 12
  return Math.round(Math.min(98, Math.max(3, score)))
}

function generateClients(count: number): Client[] {
  const rand = mulberry32(42)
  const clients: Client[] = []
  for (let i = 0; i < count; i++) {
    const first = FIRST_NAMES[Math.floor(rand() * FIRST_NAMES.length)]
    const last = LAST_NAMES[Math.floor(rand() * LAST_NAMES.length)]
    const company = COMPANIES[Math.floor(rand() * COMPANIES.length)]
    const tenureMonths = 1 + Math.floor(rand() * 71)
    const monthlyCharges = Math.round((25 + rand() * 165) * 100) / 100
    const contract = CONTRACTS[Math.floor(rand() * CONTRACTS.length)]
    const base: Omit<Client, 'riskScore' | 'id'> = {
      name: `${first} ${last}`,
      email: `${slug(first)}.${slug(last)}@${slug(company)}.fr`,
      company,
      region: REGIONS[Math.floor(rand() * REGIONS.length)],
      segment: SEGMENTS[Math.floor(rand() * SEGMENTS.length)],
      tenureMonths,
      monthlyCharges,
      totalSpend: Math.round(monthlyCharges * tenureMonths),
      contract,
      products: 1 + Math.floor(rand() * 5),
      supportTickets: Math.floor(rand() * 12),
      lastInteractionDays: Math.floor(rand() * 120),
      satisfaction: 1 + Math.floor(rand() * 6),
    }
    const riskScore = computeRisk(base, rand())
    clients.push({
      id: `CLI-${(1000 + i).toString()}`,
      ...base,
      riskScore,
    })
  }
  return clients
}

export const CLIENTS: Client[] = generateClients(124)

export function riskLevel(score: number): RiskLevel {
  if (score < 30) return 'faible'
  if (score <= 70) return 'moyen'
  return 'eleve'
}

export const RISK_LABEL: Record<RiskLevel, string> = {
  faible: 'Faible',
  moyen: 'Moyen',
  eleve: 'Élevé',
}
