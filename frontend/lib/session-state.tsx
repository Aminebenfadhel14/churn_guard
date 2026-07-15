'use client'

/**
 * État de session partagé, conservé au niveau du layout racine (qui ne se
 * démonte jamais lors d'une navigation côté client). Sans ça, chaque page
 * (Upload, Prédire, Copilot) perd son travail (résultat, conversation,
 * formulaire) dès qu'on la quitte puis qu'on y revient, car Next.js démonte
 * le composant `page.tsx` à chaque changement de route.
 */

import { createContext, type Dispatch, type ReactNode, type SetStateAction, useContext, useState } from 'react'

// ----- Upload -----

export interface ColonneDrift {
  colonne: string
  psi: number
  niveau: 'stable' | 'modere' | 'fort'
}
export interface Drift {
  niveau_global: 'stable' | 'modere' | 'fort'
  psi_moyen: number
  n_colonnes_analysees: number
  colonnes: ColonneDrift[]
}
export interface Apercu {
  fichier: string
  lignes: number
  colonnes: number
  cible_detectee: string | null
  type_probleme: string | null
  features: string[]
  entrainement?: string
  drift?: Drift | null
}
export interface ResultatModele {
  nom: string
  selectionne: boolean
  cv_roc_auc: number
  cv_f1: number
  cv_accuracy: number
  test_roc_auc: number
  test_f1: number
  test_accuracy: number
  test_precision: number
  test_recall: number
}
export interface Entrainement {
  meilleur_modele: string
  version: string
  raison_selection: string
  test_roc_auc: number
  test_f1: number
  test_accuracy: number
  modeles_compares: string[]
  resultats_modeles: ResultatModele[]
}

export interface UploadState {
  fichier: File | null
  uploading: boolean
  apercu: Apercu | null
  entrainant: boolean
  progression: string
  resultat: Entrainement | null
}

const uploadInitial: UploadState = {
  fichier: null,
  uploading: false,
  apercu: null,
  entrainant: false,
  progression: '',
  resultat: null,
}

// ----- Types partagés Prédire / Copilot -----

export interface Feature {
  nom: string
  type: 'numerique' | 'categoriel' | 'booleen' | 'date' | 'texte'
  valeurs: (string | number)[] | null
  min: number | null
  max: number | null
}

// ----- Prédire -----

export interface PredictSchema {
  cible: string | null
  type_probleme: string | null
  features: Feature[]
}
export interface PredictionResult {
  risk_score: number
  prediction: number
  risk_level: 'faible' | 'moyen' | 'eleve'
  modele: string
}
export interface Recommendation {
  action?: string
  detail?: string
  priority?: string
  impact?: number
}
export interface RetentionPlan {
  source?: string
  resume?: string
  signaux?: string[]
  etapes?: string[]
  message?: string
}
export interface EmailAlert {
  subject?: string
  body?: string
}
export interface EnrichedRecommendation {
  recommendations?: Recommendation[]
  plan_retention?: RetentionPlan
  email_alert?: EmailAlert
  source_recommendations?: string
}

export interface PredictState {
  schema: PredictSchema | null
  values: Record<string, string>
  chargement: boolean
  erreurSchema: string | null
  predicting: boolean
  erreur: string | null
  resultat: PredictionResult | null
  chargementConseil: boolean
  conseil: EnrichedRecommendation | null
  erreurConseil: string | null
  prepAlerte: boolean
  alerte: { sujet: string; corps: string } | null
  destinataire: string
}

const predictInitial: PredictState = {
  schema: null,
  values: {},
  chargement: true,
  erreurSchema: null,
  predicting: false,
  erreur: null,
  resultat: null,
  chargementConseil: false,
  conseil: null,
  erreurConseil: null,
  prepAlerte: false,
  alerte: null,
  destinataire: 'benfadhelamine9@gmail.com',
}

// ----- Copilot -----

export interface CopilotSchema {
  cible: string | null
  features: Feature[]
}
export interface Message {
  role: 'user' | 'assistant'
  content: string
}
export interface Facteur {
  feature: string
  label: string
  contribution: number
}
export interface Action {
  action?: string
  detail?: string
}
export interface ExpressResult {
  risk_score: number
  risk_level: string
  facteurs: Facteur[]
  recommendations: Action[]
  email_alerte?: { subject?: string; body?: string }
  escalade: boolean
  decision: string
  synthese: string
  source_synthese: string
}

export interface CopilotState {
  schema: CopilotSchema | null
  values: Record<string, string>
  erreurSchema: string | null
  mode: 'assistant' | 'express'
  messages: Message[]
  input: string
  sending: boolean
  running: boolean
  erreurExpress: string | null
  res: ExpressResult | null
}

const copilotInitial: CopilotState = {
  schema: null,
  values: {},
  erreurSchema: null,
  mode: 'assistant',
  messages: [],
  input: '',
  sending: false,
  running: false,
  erreurExpress: null,
  res: null,
}

// ----- Provider -----

interface SessionStateValue {
  upload: UploadState
  setUpload: Dispatch<SetStateAction<UploadState>>
  predict: PredictState
  setPredict: Dispatch<SetStateAction<PredictState>>
  copilot: CopilotState
  setCopilot: Dispatch<SetStateAction<CopilotState>>
}

const SessionStateContext = createContext<SessionStateValue | null>(null)

export function SessionStateProvider({ children }: { children: ReactNode }) {
  const [upload, setUpload] = useState<UploadState>(uploadInitial)
  const [predict, setPredict] = useState<PredictState>(predictInitial)
  const [copilot, setCopilot] = useState<CopilotState>(copilotInitial)

  return (
    <SessionStateContext.Provider
      value={{ upload, setUpload, predict, setPredict, copilot, setCopilot }}
    >
      {children}
    </SessionStateContext.Provider>
  )
}

function useSessionState(): SessionStateValue {
  const ctx = useContext(SessionStateContext)
  if (!ctx) throw new Error('useSessionState doit être utilisé sous SessionStateProvider')
  return ctx
}

/** Patch partiel pratique : `patch({ champ: valeur })` au lieu de réécrire tout l'objet. */
function creerPatch<T>(setState: Dispatch<SetStateAction<T>>) {
  return (p: Partial<T>) => setState((prev) => ({ ...prev, ...p }))
}

export function useUploadState() {
  const { upload, setUpload } = useSessionState()
  return { state: upload, setState: setUpload, patch: creerPatch(setUpload) }
}

export function usePredictState() {
  const { predict, setPredict } = useSessionState()
  return { state: predict, setState: setPredict, patch: creerPatch(setPredict) }
}

export function useCopilotState() {
  const { copilot, setCopilot } = useSessionState()
  return { state: copilot, setState: setCopilot, patch: creerPatch(setCopilot) }
}
