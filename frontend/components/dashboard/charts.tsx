'use client'

import { useRouter } from 'next/navigation'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { ScatterPoint, TrendPoint } from '@/lib/types'

const RISK_COLORS: Record<string, string> = {
  faible: 'var(--success)',
  moyen: 'var(--warning)',
  eleve: 'var(--danger)',
}

function TooltipBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      {children}
    </div>
  )
}

const axisProps = {
  stroke: 'var(--muted-foreground)',
  fontSize: 12,
  tickLine: false,
  axisLine: false,
} as const

function ChartShell({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <div className="px-2 pb-4 sm:px-4">{children}</div>
    </Card>
  )
}

export function RiskDistributionChart({
  data,
}: {
  data: { level: string; count: number; key: string }[]
}) {
  const router = useRouter()
  return (
    <ChartShell
      title="Répartition des risques"
      description="Nombre de clients par niveau de risque. Cliquez une barre pour filtrer."
    >
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="level" {...axisProps} />
          <YAxis {...axisProps} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: 'var(--muted)', opacity: 0.5 }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipBox>
                  <p className="font-medium">{payload[0].payload.level}</p>
                  <p className="text-muted-foreground">
                    {payload[0].value} clients
                  </p>
                </TooltipBox>
              ) : null
            }
          />
          <Bar
            dataKey="count"
            radius={[6, 6, 0, 0]}
            maxBarSize={90}
            className="cursor-pointer"
            onClick={(d: { key?: string }) =>
              d?.key && router.push(`/clients?risk=${d.key}`)
            }
          >
            {data.map((entry) => (
              <Cell key={entry.key} fill={RISK_COLORS[entry.key]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function ScoreHistogramChart({
  data,
}: {
  data: { tranche: string; count: number }[]
}) {
  return (
    <ChartShell
      title="Distribution des scores de risque"
      description="Nombre de clients par tranche de score de churn (%)."
    >
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="tranche" {...axisProps} interval={0} fontSize={10} />
          <YAxis {...axisProps} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: 'var(--muted)', opacity: 0.5 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox>
                  <p className="font-medium">{label} %</p>
                  <p className="text-muted-foreground">
                    {payload[0].value} clients
                  </p>
                </TooltipBox>
              ) : null
            }
          />
          <Bar
            dataKey="count"
            radius={[6, 6, 0, 0]}
            maxBarSize={48}
            fill="var(--chart-1)"
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function ChurnTrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <ChartShell
      title="Évolution du taux de churn"
      description="Taux de churn mensuel sur les 12 derniers mois (%)."
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="month" {...axisProps} />
          <YAxis {...axisProps} unit="%" domain={[0, 'dataMax + 2']} />
          <Tooltip
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox>
                  <p className="font-medium">{label}</p>
                  <p className="text-primary">
                    Churn : {payload[0].value}%
                  </p>
                </TooltipBox>
              ) : null
            }
          />
          <Line
            type="monotone"
            dataKey="churnRate"
            stroke="var(--chart-1)"
            strokeWidth={2.5}
            dot={{ r: 3, fill: 'var(--chart-1)' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function TenureScatterChart({ data }: { data: ScatterPoint[] }) {
  return (
    <ChartShell
      title="Ancienneté vs Risque"
      description="Corrélation entre l'ancienneté (mois) et le score de risque."
    >
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 8, right: 12, left: -16, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            type="number"
            dataKey="tenure"
            name="Ancienneté"
            unit=" m"
            {...axisProps}
          />
          <YAxis
            type="number"
            dataKey="risk"
            name="Risque"
            domain={[0, 100]}
            {...axisProps}
          />
          <ZAxis range={[40, 40]} />
          <Tooltip
            cursor={{ strokeDasharray: '3 3' }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipBox>
                  <p className="font-medium">{payload[0].payload.name}</p>
                  <p className="text-muted-foreground">
                    Ancienneté : {payload[0].payload.tenure} mois
                  </p>
                  <p className="text-muted-foreground">
                    Risque : {payload[0].payload.risk}
                  </p>
                </TooltipBox>
              ) : null
            }
          />
          <Scatter data={data} fill="var(--chart-2)" fillOpacity={0.55} />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}
