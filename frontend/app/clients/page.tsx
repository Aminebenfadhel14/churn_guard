'use client'

import {
  AlertCircle,
  Download,
  Loader2,
  Search,
  SlidersHorizontal,
  UploadCloud,
  Users,
} from 'lucide-react'
import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { RiskBadge } from '@/components/risk-badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAuth } from '@/lib/auth'

const PAGE_SIZE = 20

type RiskFilter = 'all' | 'faible' | 'moyen' | 'eleve'

interface ClientRow {
  id: string
  risk_score: number
  values: Record<string, string | number | boolean | null>
}

interface ClientsResponse {
  // Vrai quand l'utilisateur n'a pas encore de dataset : on affiche l'invitation
  // à importer plutôt que le tableau.
  empty?: boolean
  dataset: string
  cible: string
  id_col: string | null
  colonnes: string[]
  total: number
  offset: number
  limit: number
  clients: ClientRow[]
}

/** Formate une valeur de cellule (nombre lisible, — si vide). */
function formatVal(v: string | number | boolean | null): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') {
    return Number.isInteger(v) ? v.toLocaleString('fr-FR') : v.toFixed(2)
  }
  return String(v)
}

export default function ClientsPage() {
  const { apiFetch } = useAuth()
  const [data, setData] = useState<ClientsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const [query, setQuery] = useState('')
  const [risk, setRisk] = useState<RiskFilter>('all')
  const [page, setPage] = useState(1)

  const buildUrl = useCallback(
    (limit: number, offset: number) => {
      const params = new URLSearchParams()
      params.set('limit', String(limit))
      params.set('offset', String(offset))
      params.set('risk', risk)
      if (query.trim()) params.set('q', query.trim())
      return `/clients?${params.toString()}`
    },
    [risk, query],
  )

  const charger = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rep = await apiFetch(buildUrl(PAGE_SIZE, (page - 1) * PAGE_SIZE))
      if (!rep.ok) {
        const d = await rep.json().catch(() => ({}))
        throw new Error(d.detail ?? `Erreur ${rep.status}`)
      }
      setData(await rep.json())
    } catch (e) {
      setData(null)
      setError(
        e instanceof Error && e.message.includes('fetch')
          ? 'API injoignable (uvicorn app.main:app).'
          : (e as Error).message,
      )
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildUrl, page])

  // Recharge (avec un léger debounce) à chaque changement de filtre/page.
  useEffect(() => {
    const t = setTimeout(() => {
      void charger()
    }, 300)
    return () => clearTimeout(t)
  }, [charger])

  const onQuery = (v: string) => {
    setQuery(v)
    setPage(1)
  }
  const onRisk = (v: RiskFilter) => {
    setRisk(v)
    setPage(1)
  }

  const exporter = async () => {
    if (!data) return
    setExporting(true)
    try {
      const rep = await apiFetch(buildUrl(1_000_000, 0))
      const d: ClientsResponse = await rep.json()
      const entetes = [data.id_col ?? 'id', ...d.colonnes, 'score_risque']
      const lignes = d.clients.map((c) =>
        [c.id, ...d.colonnes.map((k) => c.values[k]), c.risk_score]
          .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`)
          .join(','),
      )
      const contenu = [entetes.join(','), ...lignes].join('\n')
      const blob = new Blob([`﻿${contenu}`], {
        type: 'text/csv;charset=utf-8;',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `churnguard_clients_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      /* ignore */
    } finally {
      setExporting(false)
    }
  }

  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const colonnes = data?.colonnes ?? []
  const estVide = !loading && !error && !!data?.empty

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Clients</h1>
          <p className="mt-1 text-muted-foreground">
            Chaque ligne de votre dataset, avec son score de churn prédit.
            {data && !data.empty && (
              <>
                {' '}
                <span className="text-foreground">
                  {data.dataset}
                </span>{' '}
                · cible : <span className="text-foreground">{data.cible}</span>
              </>
            )}
          </p>
        </div>
        <Button variant="outline" onClick={exporter} disabled={!data || exporting || estVide}>
          {exporting ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Download className="size-4" />
          )}
          Exporter CSV ({total})
        </Button>
      </div>

      {estVide ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
            <span className="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Users className="size-7" />
            </span>
            <div>
              <h2 className="text-lg font-semibold">Aucun client pour l&apos;instant</h2>
              <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
                Importez un dataset et lancez un entraînement : vos clients et leurs scores de
                churn apparaîtront ici.
              </p>
            </div>
            <Link href="/upload" className={cn(buttonVariants(), 'gap-2')}>
              <UploadCloud className="size-4" />
              Importer un dataset
            </Link>
          </CardContent>
        </Card>
      ) : (
        <>
      <Card className="mb-6">
        <CardHeader className="flex-row items-center gap-2">
          <SlidersHorizontal className="size-4 text-muted-foreground" />
          <CardTitle className="text-base">Filtres</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label className="mb-1.5 block text-xs">Recherche</Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-8"
                placeholder="ID ou valeur…"
                value={query}
                onChange={(e) => onQuery(e.target.value)}
              />
            </div>
          </div>
          <div>
            <Label className="mb-1.5 block text-xs">Niveau de risque</Label>
            <Select value={risk} onValueChange={(v) => onRisk(v as RiskFilter)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous</SelectItem>
                <SelectItem value="faible">Faible (&lt; 30 %)</SelectItem>
                <SelectItem value="moyen">Moyen (30–70 %)</SelectItem>
                <SelectItem value="eleve">Élevé (&gt; 70 %)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {error ? (
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
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{data?.id_col ?? 'ID'}</TableHead>
                  {colonnes.map((c) => (
                    <TableHead key={c} className="hidden md:table-cell">
                      {c}
                    </TableHead>
                  ))}
                  <TableHead>Risque</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading && (
                  <TableRow>
                    <TableCell
                      colSpan={colonnes.length + 2}
                      className="py-10 text-center text-muted-foreground"
                    >
                      <Loader2 className="mx-auto size-5 animate-spin" />
                    </TableCell>
                  </TableRow>
                )}
                {!loading && data?.clients.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={colonnes.length + 2}
                      className="py-10 text-center text-muted-foreground"
                    >
                      Aucun client ne correspond à ces critères.
                    </TableCell>
                  </TableRow>
                )}
                {!loading &&
                  data?.clients.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium tabular-nums">
                        {c.id}
                      </TableCell>
                      {colonnes.map((col) => (
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
      )}

      {!error && (
        <div className="mt-4 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {total} client(s) — page {Math.min(page, pages)}/{pages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Précédent
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pages || loading}
              onClick={() => setPage((p) => p + 1)}
            >
              Suivant
            </Button>
          </div>
        </div>
      )}
        </>
      )}
    </div>
  )
}
