'use client'

import {
  AlertTriangle,
  Copy,
  Lightbulb,
  Loader2,
  Mail,
  Send,
  Sparkles,
} from 'lucide-react'
import { useEffect } from 'react'
import { toast } from 'sonner'
import { RiskScoreCard } from '@/components/client/risk-score-card'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '@/lib/auth'
import {
  type EnrichedRecommendation,
  type Feature,
  type PredictSchema,
  type PredictionResult,
  type Recommendation,
  usePredictState,
} from '@/lib/session-state'

function valeurInitiale(f: Feature): string {
  if (f.type === 'categoriel' || f.type === 'booleen') {
    return f.valeurs && f.valeurs.length ? String(f.valeurs[0]) : ''
  }
  if (f.type === 'numerique') return String(f.min ?? 0)
  return ''
}

export default function PredictPage() {
  const { apiFetch } = useAuth()
  const { state, patch } = usePredictState()
  const {
    schema,
    values,
    chargement,
    erreurSchema,
    predicting,
    erreur,
    resultat,
    chargementConseil,
    conseil,
    erreurConseil,
    prepAlerte,
    alerte,
    destinataire,
  } = state

  useEffect(() => {
    if (schema) {
      patch({ chargement: false }) // déjà chargé (retour sur la page)
      return
    }
    ;(async () => {
      try {
        const rep = await apiFetch('/schema')
        if (!rep.ok) {
          const d = await rep.json().catch(() => ({}))
          throw new Error(
            rep.status === 503
              ? 'Aucun modèle entraîné. Lance `python scripts/train_model.py`.'
              : d.detail ?? `Erreur ${rep.status}`,
          )
        }
        const s: PredictSchema = await rep.json()
        const init: Record<string, string> = {}
        s.features.forEach((f) => (init[f.nom] = valeurInitiale(f)))
        patch({ schema: s, values: init })
      } catch (e) {
        patch({
          erreurSchema:
            e instanceof Error && e.message.includes('fetch')
              ? "Impossible de joindre l'API (uvicorn app.main:app)."
              : (e as Error).message,
        })
      } finally {
        patch({ chargement: false })
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const set = (nom: string, v: string) => patch({ values: { ...values, [nom]: v } })

  const chargerConseilRetention = async (
    prediction: PredictionResult,
  ): Promise<EnrichedRecommendation> => {
    const rep = await apiFetch('/recommend/enriched', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    })

    if (rep.ok) return (await rep.json()) as EnrichedRecommendation

    const fallback = await apiFetch('/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    })

    if (!fallback.ok) {
      const d = await fallback.json().catch(() => ({}))
      throw new Error(d.detail ?? `Erreur ${fallback.status}`)
    }

    const data = (await fallback.json()) as {
      recommendations?: Recommendation[]
      source_recommendations?: string
    }
    const recos = data.recommendations ?? []
    const premiereAction = recos[0]?.action ?? 'Maintenir un suivi standard'

    return {
      recommendations: recos,
      plan_retention: {
        source: 'degrade',
        resume: `Risque ${prediction.risk_level} (${prediction.risk_score}%). Action prioritaire : ${premiereAction}.`,
        etapes: recos
          .slice(0, 3)
          .map((r, i) => `${i + 1}. ${r.action ?? ''}${r.detail ? ' - ' + r.detail : ''}`),
      },
      source_recommendations: data.source_recommendations ?? 'regles_secours',
    }
  }

  /** Prépare un brouillon d'email d'alerte (aucun envoi automatique). */
  const preparerAlerte = async () => {
    if (!resultat) return
    patch({ prepAlerte: true })
    try {
      if (conseil?.email_alert?.subject && conseil.email_alert.body) {
        patch({
          alerte: {
            sujet: conseil.email_alert.subject,
            corps: conseil.email_alert.body,
          },
        })
        return
      }

      let recos: Recommendation[] = []

      try {
        const data = conseil ?? (await chargerConseilRetention(resultat))
        patch({ conseil: data })
        recos = data.recommendations ?? []
        if (data.email_alert?.subject && data.email_alert?.body) {
          patch({
            alerte: {
              sujet: data.email_alert.subject,
              corps: data.email_alert.body,
            },
          })
          return
        }
      } catch {
        /* repli local ci-dessous */
      }

      try {
        const rep = await apiFetch('/recommend', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(values),
        })
        if (rep.ok) recos = (await rep.json()).recommendations ?? []
      } catch {
        /* on garde un mail sans la section actions */
      }

      const carac = Object.entries(values)
        .map(([k, v]) => `  - ${k} : ${v}`)
        .join('\n')
      const actions = recos.length
        ? recos
            .map(
              (r, i) =>
                `  ${i + 1}. ${r.action ?? ''}${r.detail ? ' — ' + r.detail : ''}` +
                (r.priority ? ` (priorité ${r.priority})` : ''),
            )
            .join('\n')
        : '  (aucune action spécifique détectée)'

      const sujet = `Alerte churn — client a risque eleve (${resultat.risk_score}%)`
      const corps = `Bonjour,

Un client présente un risque de départ ÉLEVÉ, détecté par ChurnGuard.

Score de churn : ${resultat.risk_score}% (niveau : élevé)
Modèle utilisé : ${resultat.modele}

Caractéristiques du client :
${carac}

Actions de rétention recommandées :
${actions}

Merci de prendre contact rapidement pour éviter la perte de ce client.

— ChurnGuard`

      patch({ alerte: { sujet, corps } })
    } finally {
      patch({ prepAlerte: false })
    }
  }

  const predire = async () => {
    patch({
      predicting: true,
      erreur: null,
      resultat: null,
      conseil: null,
      erreurConseil: null,
      chargementConseil: false,
      alerte: null,
    })
    try {
      const rep = await apiFetch('/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      })
      if (!rep.ok) {
        const d = await rep.json().catch(() => ({}))
        throw new Error(d.detail ?? `Erreur ${rep.status}`)
      }
      const prediction = (await rep.json()) as PredictionResult
      patch({ resultat: prediction, predicting: false, chargementConseil: true })
      try {
        patch({ conseil: await chargerConseilRetention(prediction) })
      } catch (err) {
        patch({
          erreurConseil:
            err instanceof Error && err.message.includes('fetch')
              ? "Impossible de charger le plan de rétention."
              : (err as Error).message,
        })
      } finally {
        patch({ chargementConseil: false })
      }
    } catch (e) {
      patch({
        erreur:
          e instanceof Error && e.message.includes('fetch')
            ? "Impossible de joindre l'API (uvicorn app.main:app)."
            : (e as Error).message,
      })
    } finally {
      patch({ predicting: false })
    }
  }

  if (chargement) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> Chargement du schéma…
      </div>
    )
  }

  if (erreurSchema || !schema) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <Card className="border-danger/40">
          <CardContent className="flex items-start gap-2 pt-6 text-sm text-danger">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span>{erreurSchema ?? 'Schéma indisponible.'}</span>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          Prédire {schema.cible ? `« ${schema.cible} »` : 'le churn'}
        </h1>
        <p className="mt-1 text-muted-foreground">
          Formulaire généré automatiquement à partir du dataset actif
          ({schema.features.length} variables). Renseignez les champs et lancez la prédiction.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Caractéristiques</CardTitle>
            <CardDescription>Tous les champs sont requis.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {schema.features.map((f) => (
              <div key={f.nom}>
                <Label className="mb-1.5 block text-xs">{f.nom}</Label>
                {f.type === 'categoriel' || f.type === 'booleen' ? (
                  <Select value={values[f.nom] ?? ''} onValueChange={(v) => set(f.nom, v ?? '')}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(f.valeurs ?? []).map((v) => (
                        <SelectItem key={String(v)} value={String(v)}>{String(v)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : f.type === 'date' ? (
                  <Input type="date" value={values[f.nom] ?? ''} onChange={(e) => set(f.nom, e.target.value)} />
                ) : f.type === 'numerique' ? (
                  <Input
                    type="number"
                    value={values[f.nom] ?? ''}
                    min={f.min ?? undefined}
                    max={f.max ?? undefined}
                    onChange={(e) => set(f.nom, e.target.value)}
                  />
                ) : (
                  <Input type="text" value={values[f.nom] ?? ''} onChange={(e) => set(f.nom, e.target.value)} />
                )}
                {f.type === 'numerique' && f.min != null && f.max != null && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    entre {f.min} et {f.max}
                  </p>
                )}
              </div>
            ))}

            <div className="sm:col-span-2">
              <Button className="w-full" onClick={predire} disabled={predicting}>
                {predicting ? (
                  <><Loader2 className="size-4 animate-spin" /> Prédiction…</>
                ) : (
                  <><Sparkles className="size-4" /> Prédire</>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {erreur && (
            <Card className="border-danger/40">
              <CardContent className="flex items-start gap-2 pt-6 text-sm text-danger">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                <span>{erreur}</span>
              </CardContent>
            </Card>
          )}

          {resultat ? (
            <>
              <RiskScoreCard score={resultat.risk_score} />
              <Card>
                <CardContent className="space-y-1 pt-6 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Prédiction</span>
                    <span className="font-medium">
                      {resultat.prediction === 1 ? 'Positif (classe cible)' : 'Négatif'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Modèle utilisé</span>
                    <span className="font-medium">{resultat.modele}</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between gap-2 text-base">
                    <span className="flex items-center gap-2">
                      <Lightbulb className="size-4 text-primary" /> Plan de rétention
                    </span>
                    {conseil?.source_recommendations === 'rag' ? (
                      <span className="rounded border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-[11px] font-normal text-primary">
                        RAG · IA + playbooks
                      </span>
                    ) : conseil ? (
                      <span className="rounded border border-warning/40 bg-warning/10 px-1.5 py-0.5 text-[11px] font-normal text-warning">
                        Moteur de règles (secours)
                      </span>
                    ) : null}
                  </CardTitle>
                  <CardDescription>
                    {conseil?.source_recommendations === 'rag'
                      ? "Actions générées par l'IA à partir de tes playbooks de rétention et des facteurs de risque du client."
                      : "Actions du moteur de règles de secours (l'IA est momentanément indisponible)."}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  {chargementConseil ? (
                    <div className="flex items-center text-muted-foreground">
                      <Loader2 className="mr-2 size-4 animate-spin" /> Analyse du plan…
                    </div>
                  ) : erreurConseil ? (
                    <div className="flex items-start gap-2 text-danger">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                      <span>{erreurConseil}</span>
                    </div>
                  ) : conseil ? (
                    <>
                      <p className="leading-relaxed">
                        {conseil.plan_retention?.resume ??
                          "L'IA experte a préparé les prochaines actions de rétention."}
                      </p>
                      {(conseil.plan_retention?.signaux?.length ?? 0) > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {conseil.plan_retention?.signaux?.slice(0, 4).map((signal) => (
                            <span
                              key={signal}
                              className="rounded border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                            >
                              {signal}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="space-y-2">
                        {(conseil.recommendations ?? []).slice(0, 3).map((reco, index) => (
                          <div key={`${reco.action ?? 'action'}-${index}`} className="rounded border border-border p-2">
                            <div className="flex items-start justify-between gap-2">
                              <span className="font-medium">{reco.action}</span>
                              {reco.priority && (
                                <span className="shrink-0 rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
                                  {reco.priority}
                                </span>
                              )}
                            </div>
                            {reco.detail && (
                              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                                {reco.detail}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="text-muted-foreground">
                      Lancez une prédiction pour afficher le plan de rétention.
                    </p>
                  )}
                </CardContent>
              </Card>

              {resultat.risk_level === 'eleve' && (
                <Card className="border-danger/40">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Mail className="size-4 text-danger" /> Alerte rétention
                    </CardTitle>
                    <CardDescription>
                      Client à risque élevé. Préparez un email d&apos;alerte
                      (rien n&apos;est envoyé automatiquement).
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {!alerte ? (
                      <Button
                        className="w-full"
                        variant="outline"
                        onClick={preparerAlerte}
                        disabled={prepAlerte}
                      >
                        {prepAlerte ? (
                          <><Loader2 className="size-4 animate-spin" /> Préparation…</>
                        ) : (
                          <><Mail className="size-4" /> Préparer l&apos;alerte</>
                        )}
                      </Button>
                    ) : (
                      <>
                        <div>
                          <Label className="mb-1.5 block text-xs">Destinataire</Label>
                          <Input
                            type="email"
                            value={destinataire}
                            onChange={(e) => patch({ destinataire: e.target.value })}
                          />
                        </div>
                        <div>
                          <Label className="mb-1.5 block text-xs">Objet</Label>
                          <Input value={alerte.sujet} readOnly />
                        </div>
                        <div>
                          <Label className="mb-1.5 block text-xs">Message</Label>
                          <textarea
                            readOnly
                            value={alerte.corps}
                            rows={12}
                            className="w-full rounded-lg border border-border bg-muted/30 p-2.5 text-xs leading-relaxed"
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            className="flex-1"
                            onClick={() => {
                              navigator.clipboard
                                .writeText(`${alerte.sujet}\n\n${alerte.corps}`)
                                .then(() => toast.success('Alerte copiée'))
                                .catch(() => toast.error('Copie impossible'))
                            }}
                          >
                            <Copy className="size-4" /> Copier
                          </Button>
                          <Button
                            className="flex-1"
                            onClick={() => {
                              window.location.href = `mailto:${encodeURIComponent(destinataire)}?subject=${encodeURIComponent(alerte.sujet)}&body=${encodeURIComponent(alerte.corps)}`
                            }}
                          >
                            <Send className="size-4" /> Ouvrir dans ma messagerie
                          </Button>
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            !erreur && (
              <Card className="border-dashed">
                <CardContent className="flex h-40 items-center justify-center text-center text-sm text-muted-foreground">
                  Le score s&apos;affichera ici après la prédiction.
                </CardContent>
              </Card>
            )
          )}
        </div>
      </div>
    </div>
  )
}
