'use client'

import { Layers, Loader2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/lib/auth'

interface ModelInfo {
  version: string
  label: string
  cible: string | null
  algorithme: string | null
  n_features: number
  actif: boolean
  username: string | null
  proprietaire: string | null
}

/**
 * Sélecteur de modèle actif.
 *
 * Liste les modèles entraînés (GET /models, déjà filtrés côté serveur : un
 * opérateur ne voit que les siens, un admin voit ceux de son organisation) et
 * bascule l'actif (POST /models/activate) sans ré-entraîner. Un admin peut
 * aussi supprimer un modèle (DELETE /models/{version}). Se rafraîchit tout
 * seul toutes les 10s pour qu'un entraînement lancé ailleurs apparaisse sans
 * recharger la page.
 */
export function ModelSelector() {
  const { apiFetch, user } = useAuth()
  const [models, setModels] = useState<ModelInfo[]>([])
  const [active, setActive] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [aSupprimer, setASupprimer] = useState<ModelInfo | null>(null)
  const [suppression, setSuppression] = useState(false)

  useEffect(() => {
    // Réinitialise la liste tout de suite : évite d'afficher un instant les
    // modèles de l'identité précédente pendant que la nouvelle requête part
    // (visible lors d'un changement de compte via l'impersonation).
    setModels([])
    setActive('')

    let annule = false
    const charger = () => {
      apiFetch('/models')
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((d) => {
          if (annule) return
          setModels(d.models ?? [])
          setActive(d.active ?? '')
        })
        .catch(() => {})
    }
    charger()
    // Sondage périodique : un modèle entraîné pendant qu'on est sur une autre
    // page (ou par quelqu'un d'autre) apparaît ici sans recharger la page.
    const intervalle = setInterval(charger, 10_000)
    return () => {
      annule = true
      clearInterval(intervalle)
    }
    // Redémarre le chargement (et le sondage) à chaque changement d'identité
    // (connexion, déconnexion, "se connecter en tant que" / retour) : sinon
    // apiFetch garde le token de la session active au premier montage, et le
    // menu continue d'afficher les modèles de l'ancienne identité.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.username])

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

  async function supprimer() {
    if (!aSupprimer || suppression) return
    setSuppression(true)
    try {
      const r = await apiFetch(`/models/${encodeURIComponent(aSupprimer.version)}`, {
        method: 'DELETE',
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(d.detail ?? 'Impossible de supprimer ce modèle.')
      toast.success('Modèle supprimé')
      setModels((prev) => prev.filter((m) => m.version !== aSupprimer.version))
      setASupprimer(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setSuppression(false)
    }
  }

  if (models.length === 0) return null

  // Un modèle par type de dataset (cible) ET par propriétaire : les
  // ré-entraînements d'un même dataset par la même personne se rejoignent
  // (on garde l'actif, sinon le plus récent), mais deux utilisateurs
  // différents entraînant un dataset au même libellé restent deux entrées
  // distinctes — sinon un admin ne verrait que l'une des deux dans la liste.
  const parDataset = new Map<string, ModelInfo>()
  for (const m of models) {
    const cle = `${m.username ?? '—'}::${m.label ?? m.version}`
    const existant = parDataset.get(cle)
    if (!existant || m.actif) parDataset.set(cle, m)
  }
  const options = [...parDataset.values()]
  const libelleActif = options.find((m) => m.version === active)?.label ?? options[0]?.label ?? '—'
  // N'affiche le nom du propriétaire que pour un admin voyant les modèles de
  // plusieurs personnes (inutile de le répéter si tout appartient au même).
  const plusieursProprietaires =
    user?.role === 'admin' && new Set(options.map((m) => m.username ?? '')).size > 1

  return (
    <>
      <DropdownMenu>
        {/* base-ui : le Trigger rend lui-même un <button> — on le style
            directement au lieu d'imbriquer un <Button> (voir app-header.tsx). */}
        <DropdownMenuTrigger
          aria-label="Modèle actif"
          title="Modèle actif — bascule sans ré-entraîner"
          className="hidden items-center gap-2 rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-60 sm:inline-flex"
        >
          <Layers className="size-4 text-muted-foreground" />
          <span className="max-w-[10rem] truncate">{libelleActif}</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          {options.map((m) => (
            <DropdownMenuItem
              key={m.version}
              onClick={() => changer(m.version)}
              className="flex items-center justify-between gap-2"
            >
              <span className="min-w-0 flex-1">
                <span className={`block truncate ${m.version === active ? 'font-semibold' : ''}`}>
                  {m.label}
                </span>
                {plusieursProprietaires && (
                  <span className="block truncate text-xs text-muted-foreground">
                    {m.proprietaire ?? m.username ?? 'Utilisateur inconnu'}
                  </span>
                )}
              </span>
              {user?.role === 'admin' && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setASupprimer(m)
                  }}
                  aria-label={`Supprimer ${m.label}`}
                  className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="size-3.5" />
                </button>
              )}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={!!aSupprimer} onOpenChange={(open) => !open && setASupprimer(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer ce modèle ?</DialogTitle>
            <DialogDescription>
              Le modèle <strong>{aSupprimer?.label}</strong> sera définitivement supprimé. Cette action
              est irréversible.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setASupprimer(null)} disabled={suppression}>
              Annuler
            </Button>
            <Button variant="destructive" onClick={supprimer} disabled={suppression}>
              {suppression ? <Loader2 className="size-4 animate-spin" /> : null}
              Supprimer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
