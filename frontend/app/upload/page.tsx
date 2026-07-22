'use client'

import {
  AlertTriangle,
  CheckCircle2,
  FileUp,
  Loader2,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  X,
} from 'lucide-react'
import Link from 'next/link'
import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAuth } from '@/lib/auth'
import { type Apercu, type Drift, type Entrainement, type Qualite, useUploadState } from '@/lib/session-state'

const EXT_OK = ['.csv', '.xlsx', '.xls', '.parquet']

interface EtatEntrainement {
  statut: 'idle' | 'en_cours' | 'termine' | 'echec'
  message: string
  resultat: Entrainement | null
  erreur: string | null
}

function formatTaille(o: number): string {
  if (o < 1024) return `${o} o`
  if (o < 1024 * 1024) return `${(o / 1024).toFixed(1)} Ko`
  return `${(o / (1024 * 1024)).toFixed(2)} Mo`
}

const attendre = (ms: number) => new Promise((r) => setTimeout(r, ms))
const score = (v: number) => Number.isFinite(v) ? v.toFixed(4) : '—'

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [survol, setSurvol] = useState(false)
  const { apiFetch } = useAuth()

  const { state, patch } = useUploadState()
  const { fichier, uploading, apercu, entrainant, progression, resultat } = state

  // Empêche deux boucles de suivi simultanées.
  const suiviActif = useRef(false)

  const extOk = (nom: string) => EXT_OK.some((e) => nom.toLowerCase().endsWith(e))

  /** Interroge périodiquement /train/status jusqu'à la fin de l'entraînement. */
  const suivreEntrainement = async () => {
    if (suiviActif.current) return
    suiviActif.current = true
    patch({ entrainant: true, resultat: null, progression: 'Entraînement en cours… (comparaison des modèles)' })

    const MAX_TENTATIVES = 240 // ~10 min à 2,5 s d'intervalle
    try {
      for (let i = 0; i < MAX_TENTATIVES; i++) {
        await attendre(2500)
        let etat: EtatEntrainement
        try {
          const rep = await apiFetch('/train/status')
          etat = await rep.json()
        } catch {
          continue // erreur réseau transitoire : on réessaie
        }
        if (etat.message) patch({ progression: etat.message })

        if (etat.statut === 'termine' && etat.resultat) {
          patch({ resultat: etat.resultat })
          toast.success('Modèle entraîné et activé', {
            description: etat.resultat.meilleur_modele,
          })
          return
        }
        if (etat.statut === 'echec') {
          toast.error("Échec de l'entraînement", {
            description: etat.erreur ?? 'Erreur inconnue',
          })
          return
        }
      }
      toast.error('Entraînement trop long', {
        description: 'Le suivi a expiré. Vérifiez le terminal de l’API.',
      })
    } finally {
      patch({ entrainant: false })
      suiviActif.current = false
    }
  }

  /** Déclenche l'entraînement (au clic) puis suit sa progression. */
  const lancerEntrainement = async () => {
    if (!apercu || suiviActif.current) return
    patch({ resultat: null })
    try {
      const rep = await apiFetch('/train/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fichier: apercu.fichier }),
      })
      if (!rep.ok) {
        const d = await rep.json().catch(() => ({}))
        throw new Error(d.detail ?? `Erreur ${rep.status}`)
      }
      suivreEntrainement()
    } catch (e) {
      toast.error("Impossible de lancer l'entraînement", {
        description:
          e instanceof Error && e.message.includes('fetch')
            ? 'API injoignable (uvicorn app.main:app).'
            : (e as Error).message,
      })
    }
  }

  const choisir = async (f: File | undefined) => {
    if (!f) return
    if (!extOk(f.name)) {
      toast.error('Format non supporté', { description: `Acceptés : ${EXT_OK.join(', ')}` })
      return
    }
    // Upload immédiat : le backend déclenche automatiquement l'entraînement.
    patch({ fichier: f, apercu: null, resultat: null, progression: '', uploading: true })
    try {
      const fd = new FormData()
      fd.append('file', f)
      const rep = await apiFetch('/upload', { method: 'POST', body: fd })
      if (!rep.ok) {
        const d = await rep.json().catch(() => ({}))
        throw new Error(d.detail ?? `Erreur ${rep.status}`)
      }
      const data: Apercu = await rep.json()
      patch({ apercu: data })
      toast.success('Fichier importé', {
        description: "Vérifiez le schéma puis lancez l'entraînement.",
      })

      if (!data.cible_detectee) {
        toast.warning('Aucune cible détectée', {
          description: "L'entraînement sera désactivé pour ce fichier.",
        })
      }

      if (data.drift?.niveau_global === 'fort') {
        toast.warning('Dérive de distribution détectée', {
          description:
            'Ce dataset diffère nettement de celui du modèle actif. Un réentraînement est recommandé.',
        })
      }
    } catch (e) {
      toast.error("Échec de l'upload", {
        description:
          e instanceof Error && e.message.includes('fetch')
            ? "API injoignable (uvicorn app.main:app)."
            : (e as Error).message,
      })
      patch({ fichier: null })
    } finally {
      patch({ uploading: false })
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Importer un dataset</h1>
        <p className="mt-1 text-muted-foreground">
          Déposez un fichier (CSV, Excel, Parquet) : la plateforme détecte le schéma.
          Vérifiez-le, puis lancez l&apos;entraînement quand vous êtes prêt.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">1. Fichier source</CardTitle>
          <CardDescription>Glissez-déposez ou cliquez pour parcourir.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setSurvol(true) }}
            onDragLeave={() => setSurvol(false)}
            onDrop={(e) => { e.preventDefault(); setSurvol(false); choisir(e.dataTransfer.files?.[0]) }}
            className={
              'flex w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ' +
              (survol ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50 hover:bg-muted/40')
            }
          >
            <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              {uploading ? <Loader2 className="size-6 animate-spin" /> : <UploadCloud className="size-6" />}
            </span>
            <span className="font-medium">{uploading ? 'Import en cours…' : 'Déposez votre fichier ici'}</span>
            <span className="text-sm text-muted-foreground">{EXT_OK.join(', ')}</span>
          </button>
          <input
            ref={inputRef}
            type="file"
            accept={EXT_OK.join(',')}
            className="hidden"
            onChange={(e) => choisir(e.target.files?.[0])}
          />

          {fichier && (
            <div className="flex items-center gap-3 rounded-lg border border-border p-3">
              <span className="flex size-9 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <FileUp className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{fichier.name}</div>
                <div className="text-xs text-muted-foreground">{formatTaille(fichier.size)}</div>
              </div>
              {!uploading && !entrainant && (
                <Button variant="ghost" size="icon" aria-label="Retirer"
                  onClick={() => patch({ fichier: null, apercu: null, resultat: null, progression: '' })}>
                  <X className="size-4" />
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {apercu && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-base">2. Schéma détecté</CardTitle>
            <CardDescription>Vérifié automatiquement à partir du fichier.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <Info label="Lignes" valeur={apercu.lignes.toLocaleString()} />
              <Info label="Colonnes" valeur={String(apercu.colonnes)} />
              <Info label="Cible détectée" valeur={apercu.cible_detectee ?? '(non détectée)'} />
              <Info label="Type" valeur={apercu.type_probleme ?? '—'} />
            </div>
            <div>
              <div className="mb-1 text-xs text-muted-foreground">Variables ({apercu.features.length})</div>
              <div className="flex flex-wrap gap-1.5">
                {apercu.features.map((f) => (
                  <span key={f} className="rounded-full bg-muted px-2 py-0.5 text-xs">{f}</span>
                ))}
              </div>
            </div>

            {apercu.qualite && <QualiteCard qualite={apercu.qualite} cible={apercu.cible_detectee} />}

            {apercu.drift && <DriftCard drift={apercu.drift} />}

            {entrainant ? (
              <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-primary">
                <Loader2 className="size-4 animate-spin" />
                <span className="text-sm">{progression || 'Entraînement en cours…'}</span>
              </div>
            ) : (
              <Button
                className="w-full"
                onClick={lancerEntrainement}
                disabled={!apercu.cible_detectee}
              >
                <Sparkles className="size-4" /> Lancer l&apos;entraînement
              </Button>
            )}
            {!apercu.cible_detectee && (
              <p className="text-xs text-danger">
                Aucune cible détectée automatiquement — l&apos;entraînement ne peut pas démarrer.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {resultat && (
        <Card className="mt-4 border-success/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="size-4 text-success" /> 3. Modèle entraîné & activé
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <Info label="Meilleur modèle" valeur={resultat.meilleur_modele} />
              <Info label="Version" valeur={resultat.version} />
              <Info label="ROC-AUC (test)" valeur={String(resultat.test_roc_auc)} />
              <Info label="F1 (test)" valeur={String(resultat.test_f1)} />
              <Info label="Accuracy (test)" valeur={String(resultat.test_accuracy)} />
            </div>
            <div className="rounded-lg border border-border bg-muted/20 p-3">
              <div className="mb-1 text-xs font-medium text-foreground">Pourquoi ce modèle</div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {resultat.raison_selection}
              </p>
            </div>
            {resultat.resultats_modeles?.length > 0 && (
              <div className="rounded-lg border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Modèle</TableHead>
                      <TableHead className="text-right">ROC-AUC</TableHead>
                      <TableHead className="text-right">F1</TableHead>
                      <TableHead className="text-right">Accuracy</TableHead>
                      <TableHead className="text-right">Précision</TableHead>
                      <TableHead className="text-right">Rappel</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {resultat.resultats_modeles.map((modele) => (
                      <TableRow key={modele.nom}>
                        <TableCell className="font-medium">
                          <span className="inline-flex items-center gap-2">
                            {modele.nom}
                            {modele.selectionne && <Badge>Choisi</Badge>}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">{score(modele.test_roc_auc)}</TableCell>
                        <TableCell className="text-right">{score(modele.test_f1)}</TableCell>
                        <TableCell className="text-right">{score(modele.test_accuracy)}</TableCell>
                        <TableCell className="text-right">{score(modele.test_precision)}</TableCell>
                        <TableCell className="text-right">{score(modele.test_recall)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
            <Link href="/predict" className={buttonVariants({ className: 'w-full' })}>
              <Sparkles className="size-4" /> Aller prédire
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function Info({ label, valeur }: { label: string; valeur: string }) {
  return (
    <div className="rounded-lg bg-muted/50 p-2.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-medium">{valeur}</div>
    </div>
  )
}

const NIVEAU_STYLE: Record<'equilibre' | 'modere' | 'fort', { texte: string; barre: string; libelle: string }> = {
  equilibre: { texte: 'text-success', barre: 'bg-success', libelle: 'Classes équilibrées' },
  modere: { texte: 'text-warning', barre: 'bg-warning', libelle: 'Déséquilibre modéré' },
  fort: { texte: 'text-danger', barre: 'bg-danger', libelle: 'Déséquilibre fort' },
}

function barreManquant(taux: number): string {
  if (taux >= 30) return 'bg-danger'
  if (taux >= 10) return 'bg-warning'
  return 'bg-muted-foreground/40'
}

/** Qualité des données avant entraînement : valeurs manquantes + équilibre des
 * classes de la cible — pour repérer un problème avant de lancer un
 * entraînement de plusieurs minutes pour rien. */
function QualiteCard({ qualite, cible }: { qualite: Qualite; cible: string | null }) {
  const { colonnes_manquantes, colonnes_critiques, equilibre_classes } = qualite
  const rien = colonnes_manquantes.length === 0 && !equilibre_classes

  if (rien) {
    return (
      <div className="rounded-lg border border-success/40 bg-success/5 p-3 text-sm text-success">
        <div className="flex items-center gap-2 font-medium">
          <ShieldCheck className="size-4" />
          Aucune valeur manquante, classes équilibrées.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3 rounded-lg border border-border p-3 text-sm">
      {equilibre_classes && (
        <div>
          <div
            className={`flex items-center gap-2 font-medium ${NIVEAU_STYLE[equilibre_classes.niveau].texte}`}
          >
            {equilibre_classes.niveau === 'equilibre' ? (
              <ShieldCheck className="size-4" />
            ) : (
              <AlertTriangle className="size-4" />
            )}
            {NIVEAU_STYLE[equilibre_classes.niveau].libelle}
            {cible && <span className="font-normal text-muted-foreground">— colonne « {cible} »</span>}
          </div>
          <ul className="mt-2 space-y-1.5">
            {equilibre_classes.repartition.map((r) => (
              <li key={r.classe} className="flex items-center gap-2 text-xs">
                <span className="w-20 shrink-0 truncate text-foreground/80">{r.classe}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <span
                    className={`block h-full rounded-full ${NIVEAU_STYLE[equilibre_classes.niveau].barre}`}
                    style={{ width: `${Math.max(r.pourcentage, 2)}%` }}
                  />
                </span>
                <span className="w-12 shrink-0 text-right text-muted-foreground">{r.pourcentage}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {colonnes_manquantes.length > 0 && (
        <div>
          <div
            className={`flex items-center gap-2 font-medium ${colonnes_critiques.length > 0 ? 'text-danger' : 'text-warning'}`}
          >
            <AlertTriangle className="size-4" />
            Valeurs manquantes ({colonnes_manquantes.length} colonne
            {colonnes_manquantes.length > 1 ? 's' : ''})
          </div>
          <ul className="mt-2 space-y-1.5">
            {colonnes_manquantes.slice(0, 5).map((c) => (
              <li key={c.colonne} className="flex items-center gap-2 text-xs">
                <span className="w-20 shrink-0 truncate text-foreground/80">{c.colonne}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <span
                    className={`block h-full rounded-full ${barreManquant(c.taux_manquant)}`}
                    style={{ width: `${Math.max(c.taux_manquant, 2)}%` }}
                  />
                </span>
                <span className="w-12 shrink-0 text-right text-muted-foreground">
                  {c.taux_manquant}%
                </span>
              </li>
            ))}
          </ul>
          {colonnes_manquantes.length > 5 && (
            <p className="mt-1.5 text-xs text-muted-foreground">
              + {colonnes_manquantes.length - 5} autre{colonnes_manquantes.length - 5 > 1 ? 's' : ''}{' '}
              colonne{colonnes_manquantes.length - 5 > 1 ? 's' : ''}.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

const DRIFT_STYLE: Record<Drift['niveau_global'], { classe: string; libelle: string }> = {
  stable: { classe: 'border-success/40 bg-success/5 text-success', libelle: 'Distribution stable' },
  modere: { classe: 'border-warning/40 bg-warning/5 text-warning', libelle: 'Dérive modérée' },
  fort: { classe: 'border-danger/40 bg-danger/5 text-danger', libelle: 'Dérive forte' },
}

/** Compare la distribution du fichier importé à celle du dataset d'entraînement
 * du modèle actif (Population Stability Index). Absent si aucun modèle actif. */
function DriftCard({ drift }: { drift: Drift }) {
  const style = DRIFT_STYLE[drift.niveau_global] ?? DRIFT_STYLE.stable
  const colonnesUtiles = drift.colonnes.filter((c) => c.niveau !== 'stable').slice(0, 5)

  return (
    <div className={`rounded-lg border p-3 text-sm ${style.classe}`}>
      <div className="flex items-center gap-2 font-medium">
        {drift.niveau_global === 'stable' ? (
          <ShieldCheck className="size-4" />
        ) : (
          <AlertTriangle className="size-4" />
        )}
        {style.libelle} vs. le modèle actif (PSI moyen : {drift.psi_moyen.toFixed(3)})
      </div>
      {colonnesUtiles.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs text-foreground/80">
          {colonnesUtiles.map((c) => (
            <li key={c.colonne}>
              <span className="font-medium">{c.colonne}</span> — PSI {c.psi.toFixed(3)} ({c.niveau})
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-xs text-foreground/70">
          Aucune colonne ne s&apos;écarte significativement du dataset d&apos;entraînement.
        </p>
      )}
      {drift.niveau_global !== 'stable' && (
        <p className="mt-2 text-xs text-foreground/70">
          Le modèle actif a été entraîné sur des données différentes de ce fichier :
          ses prédictions peuvent être moins fiables. Réentraînez si vous confirmez
          l&apos;import.
        </p>
      )}
    </div>
  )
}
