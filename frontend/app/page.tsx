'use client'

import { AlertCircle, Loader2 } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import {
  RiskDistributionChart,
  ScoreHistogramChart,
} from '@/components/dashboard/charts'
import { KpiCards } from '@/components/dashboard/kpi-cards'
import { RiskBadge } from '@/components/risk-badge'
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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000'

interface Dashboard {
  dataset: string
  cible: string
  stats: {
    total: number
    at_risk_count: number
    at_risk_pct: number
    avg_churn_rate: number
    avg_score: number
  }
  distribution: { level: string; count: number; key: string }[]
  histogram: { tranche: string; count: number }[]
  id_col: string | null
  colonnes: string[]
  top_clients: {
    id: string
    risk_score: number
    values: Record<string, string | number | boolean | null>
  }[]
}

function formatVal(v: string | number | boolean | null): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') {
    return Number.isInteger(v) ? v.toLocaleString('fr-FR') : v.toFixed(2)
  }
  return String(v)
}

export default function DashboardPage() {
  const [d, setD] = useState<Dashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let annule = false
    void (async () => {
      setLoading(true)
      setError(null)
      try {
        const rep = await fetch(`${API_URL}/dashboard`)
        if (!rep.ok) {
          const j = await rep.json().catch(() => ({}))
          throw new Error(j.detail ?? `Erreur ${rep.status}`)
        }
        const data = (await rep.json()) as Dashboard
        if (!annule) setD(data)
      } catch (e) {
        if (!annule)
          setError(
            e instanceof Error && e.message.includes('fetch')
              ? 'API injoignable (uvicorn app.main:app).'
              : (e as Error).message,
          )
      } finally {
        if (!annule) setLoading(false)
      }
    })()
    return () => {
      annule = true
    }
  }, [])

  const stats = d
    ? {
        totalClients: d.stats.total,
        atRiskCount: d.stats.at_risk_count,
        atRiskPct: d.stats.at_risk_pct,
        avgChurnRate: d.stats.avg_churn_rate,
        avgRiskScore: d.stats.avg_score,
      }
    : null

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-balance">
          Tableau de bord
        </h1>
        <p className="mt-1 text-muted-foreground">
          Vue d&apos;ensemble des risques d&apos;attrition, calculée sur votre
          dataset.
          {d && (
            <>
              {' '}
              <span className="text-foreground">{d.dataset}</span> · cible :{' '}
              <span className="text-foreground">{d.cible}</span>
            </>
          )}
        </p>
      </div>

      {loading && (
        <div className="flex justify-center py-20 text-muted-foreground">
          <Loader2 className="size-6 animate-spin" />
        </div>
      )}

      {error && !loading && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <AlertCircle className="size-8 text-danger" />
            <div className="font-medium">{error}</div>
            <p className="max-w-md text-sm text-muted-foreground">
              Vérifiez que l&apos;API tourne, puis importez un dataset et lancez
              un entraînement depuis la page Upload.
            </p>
          </CardContent>
        </Card>
      )}

      {d && stats && !loading && (
        <>
          <KpiCards stats={stats} />

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RiskDistributionChart data={d.distribution} />
            <ScoreHistogramChart data={d.histogram} />
          </div>

          <div className="mt-6">
            <Card className="overflow-hidden">
              <CardHeader className="flex-row items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-base">
                    Top 10 clients à risque
                  </CardTitle>
                  <CardDescription>
                    Priorisez vos actions de rétention.
                  </CardDescription>
                </div>
                <Link
                  href="/clients?risk=eleve"
                  className="whitespace-nowrap text-sm font-medium text-primary hover:underline"
                >
                  Voir tout
                </Link>
              </CardHeader>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead>{d.id_col ?? 'ID'}</TableHead>
                      {d.colonnes.map((c) => (
                        <TableHead key={c} className="hidden md:table-cell">
                          {c}
                        </TableHead>
                      ))}
                      <TableHead>Risque</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {d.top_clients.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-medium tabular-nums">
                          {c.id}
                        </TableCell>
                        {d.colonnes.map((col) => (
                          <TableCell
                            key={col}
                            className="hidden md:table-cell text-muted-foreground"
                          >
                            {formatVal(c.values[col])}
                          </TableCell>
                        ))}
                        <TableCell>
                          <RiskBadge score={c.risk_score} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
