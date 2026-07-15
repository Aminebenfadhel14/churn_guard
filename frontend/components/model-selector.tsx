'use client'

import { Layers } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth'

interface ModelInfo {
  version: string
  label: string
  cible: string | null
  algorithme: string | null
  n_features: number
  actif: boolean
}

/**
 * Sélecteur de modèle actif.
 *
 * Liste les modèles entraînés (GET /models) et bascule l'actif (POST
 * /models/activate) sans ré-entraîner. Après bascule, on recharge la page pour
 * que dashboard, clients, prédiction et schéma reflètent le nouveau modèle.
 */
export function ModelSelector() {
  const { apiFetch } = useAuth()
  const [models, setModels] = useState<ModelInfo[]>([])
  const [active, setActive] = useState<string>('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let annule = false
    apiFetch('/models')
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => {
        if (annule) return
        setModels(d.models ?? [])
        setActive(d.active ?? '')
      })
      .catch(() => {})
    return () => {
      annule = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function changer(version: string) {
    if (!version || version === active || busy) return
    setBusy(true)
    try {
      const r = await apiFetch('/models/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version }),
      })
      if (!r.ok) throw new Error(String(r.status))
      window.location.reload()
    } catch {
      setBusy(false)
    }
  }

  if (models.length === 0) return null

  // Un modèle par type de dataset (cible) : on garde l'actif s'il existe pour
  // cette cible, sinon le plus récent (la liste arrive déjà triée récente d'abord).
  const parDataset = new Map<string, ModelInfo>()
  for (const m of models) {
    // On regroupe par LABEL (identité du dataset) : les ré-entraînements d'un
    // même dataset se rejoignent, mais deux datasets différents (même si leur
    // cible s'appelle "Churn") restent des entrées distinctes.
    const cle = m.label ?? m.version
    const existant = parDataset.get(cle)
    if (!existant || m.actif) parDataset.set(cle, m)
  }
  const options = [...parDataset.values()]

  return (
    <label
      className="hidden items-center gap-2 rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm sm:inline-flex"
      title="Modèle actif — bascule banque / RH sans ré-entraîner"
    >
      <Layers className="size-4 text-muted-foreground" />
      <select
        aria-label="Modèle actif"
        value={active}
        disabled={busy}
        onChange={(e) => changer(e.target.value)}
        className="max-w-[12rem] cursor-pointer truncate bg-transparent text-sm font-medium text-foreground focus:outline-none disabled:opacity-60"
      >
        {options.map((m) => (
          <option key={m.version} value={m.version}>
            {m.label}
          </option>
        ))}
      </select>
    </label>
  )
}
