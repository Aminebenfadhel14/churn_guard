'use client'

import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Check,
  Lightbulb,
  Mail,
  RotateCcw,
} from 'lucide-react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useMemo, useState } from 'react'
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
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import {
  explainClient,
  getClient,
  recommendClient,
  simulateScore,
} from '@/lib/api'
import { riskLevel } from '@/lib/mock-data'
import type { Client } from '@/lib/types'

const PRIORITY_STYLE: Record<string, string> = {
  Haute: 'bg-danger/15 text-danger',
  Moyenne: 'bg-warning/15 text-warning',
  Basse: 'bg-muted text-muted-foreground',
}

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const client = getClient(id)

  if (!client) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <p className="text-lg font-medium">Client introuvable</p>
        <p className="mt-1 text-muted-foreground">
          Aucun client avec l&apos;identifiant « {id} ».
        </p>
        <Button asChild className="mt-6" variant="outline">
          <Link href="/clients"><ArrowLeft className="size-4" /> Retour aux clients</Link>
        </Button>
      </div>
    )
  }

  const shap = explainClient(client)
  const recos = recommendClient(client)

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <Link
        href="/clients"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Retour aux clients
      </Link>

      {/* Identité */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{client.name}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span>{client.id}</span>
            <span className="inline-flex items-center gap-1">
              <Mail className="size-3.5" /> {client.email}
            </span>
            <span>{client.company}</span>
            <span>{client.segment} · {client.region}</span>
            <span>{client.tenureMonths} mois d&apos;ancienneté</span>
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Colonne gauche : score + SHAP */}
        <div className="space-y-4 lg:col-span-2">
          <RiskScoreCard score={client.riskScore} />

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pourquoi ce score ? (SHAP)</CardTitle>
              <CardDescription>
                Les 5 facteurs les plus influents sur le risque de ce client.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {shap.map((f) => {
                const augmente = f.contribution > 0
                return (
                  <div key={f.feature} className="flex items-start gap-3">
                    <span
                      className={
                        'mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full ' +
                        (augmente
                          ? 'bg-danger/15 text-danger'
                          : 'bg-success/15 text-success')
                      }
                    >
                      {augmente ? <ArrowUp className="size-4" /> : <ArrowDown className="size-4" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{f.label}</span>
                        <span
                          className={
                            'tabular-nums text-sm font-semibold ' +
                            (augmente ? 'text-danger' : 'text-success')
                          }
                        >
                          {augmente ? '+' : ''}{f.contribution}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">{f.description}</p>
                    </div>
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </div>

        {/* Colonne droite : recommandations + what-if */}
        <div className="space-y-4">
          <RecommendationsCard recos={recos} />
          <WhatIfCard client={client} />
        </div>
      </div>
    </div>
  )
}

function RecommendationsCard({
  recos,
}: {
  recos: ReturnType<typeof recommendClient>
}) {
  const [faites, setFaites] = useState<Set<string>>(new Set())

  const marquer = (id: string, action: string) => {
    setFaites((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
        toast.success('Action marquée comme faite', { description: action })
      }
      return next
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Lightbulb className="size-4 text-primary" /> Actions recommandées
        </CardTitle>
        <CardDescription>Classées par priorité.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {recos.map((r) => {
          const fait = faites.has(r.id)
          return (
            <div
              key={r.id}
              className={
                'rounded-lg border p-3 transition-colors ' +
                (fait ? 'border-success/40 bg-success/5' : 'border-border')
              }
            >
              <div className="flex items-start justify-between gap-2">
                <span className={'text-sm rounded-full px-2 py-0.5 font-medium ' + PRIORITY_STYLE[r.priority]}>
                  {r.priority}
                </span>
                <span className="tabular-nums text-xs text-success">
                  −{r.impact} pts
                </span>
              </div>
              <p className={'mt-2 font-medium ' + (fait ? 'line-through text-muted-foreground' : '')}>
                {r.action}
              </p>
              <p className="text-sm text-muted-foreground">{r.detail}</p>
              <Button
                variant={fait ? 'secondary' : 'outline'}
                size="sm"
                className="mt-2 w-full"
                onClick={() => marquer(r.id, r.action)}
              >
                <Check className="size-4" /> {fait ? 'Fait' : 'Marquer comme fait'}
              </Button>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

function WhatIfCard({ client }: { client: Client }) {
  const [satisfaction, setSatisfaction] = useState(client.satisfaction)
  const [supportTickets, setSupportTickets] = useState(client.supportTickets)
  const [lastInteractionDays, setLast] = useState(client.lastInteractionDays)
  const [products, setProducts] = useState(client.products)
  const [contract, setContract] = useState<Client['contract']>(client.contract)

  const scoreSimule = useMemo(
    () =>
      simulateScore(client, {
        satisfaction,
        supportTickets,
        lastInteractionDays,
        products,
        contract,
      }),
    [client, satisfaction, supportTickets, lastInteractionDays, products, contract],
  )

  const delta = scoreSimule - client.riskScore
  const level = riskLevel(scoreSimule)
  const couleur =
    level === 'faible' ? 'text-success' : level === 'moyen' ? 'text-warning' : 'text-danger'

  const reset = () => {
    setSatisfaction(client.satisfaction)
    setSupportTickets(client.supportTickets)
    setLast(client.lastInteractionDays)
    setProducts(client.products)
    setContract(client.contract)
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle className="text-base">Simulation « What-if »</CardTitle>
          <CardDescription>Ajustez et voyez le score recalculé.</CardDescription>
        </div>
        <Button variant="ghost" size="icon" aria-label="Réinitialiser" onClick={reset}>
          <RotateCcw className="size-4" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-lg bg-muted/50 p-4 text-center">
          <div className="text-xs text-muted-foreground">Score simulé</div>
          <div className={'text-4xl font-semibold tabular-nums ' + couleur}>
            {scoreSimule}
          </div>
          <div className="mt-1 text-sm tabular-nums text-muted-foreground">
            {delta === 0 ? 'Inchangé' : delta > 0 ? `+${delta} pts (risque accru)` : `${delta} pts (risque réduit)`}
          </div>
        </div>

        <SliderRow
          label={`Satisfaction : ${satisfaction}/6`}
          min={1} max={6} step={1} value={satisfaction} onChange={setSatisfaction}
        />
        <SliderRow
          label={`Tickets support : ${supportTickets}`}
          min={0} max={15} step={1} value={supportTickets} onChange={setSupportTickets}
        />
        <SliderRow
          label={`Jours depuis interaction : ${lastInteractionDays}`}
          min={0} max={120} step={1} value={lastInteractionDays} onChange={setLast}
        />
        <SliderRow
          label={`Produits souscrits : ${products}`}
          min={1} max={6} step={1} value={products} onChange={setProducts}
        />

        <div>
          <Label className="mb-1.5 block text-xs">Type de contrat</Label>
          <Select value={contract} onValueChange={(v) => setContract(v as Client['contract'])}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="Mensuel">Mensuel</SelectItem>
              <SelectItem value="Annuel">Annuel</SelectItem>
              <SelectItem value="Bi-annuel">Bi-annuel</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  )
}

function SliderRow({
  label, min, max, step, value, onChange,
}: {
  label: string
  min: number
  max: number
  step: number
  value: number
  onChange: (v: number) => void
}) {
  return (
    <div>
      <Label className="mb-2 block text-xs">{label}</Label>
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={(v) => onChange(v[0])}
      />
    </div>
  )
}
