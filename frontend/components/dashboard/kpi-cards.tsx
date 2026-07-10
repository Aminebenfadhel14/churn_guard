import {
  AlertTriangle,
  Gauge,
  TrendingDown,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { DashboardStats } from '@/lib/types'
import { cn } from '@/lib/utils'

interface Kpi {
  label: string
  value: string
  hint: string
  icon: LucideIcon
  accent: string
  iconWrap: string
}

export function KpiCards({ stats }: { stats: DashboardStats }) {
  const kpis: Kpi[] = [
    {
      label: 'Clients totaux',
      value: stats.totalClients.toLocaleString('fr-FR'),
      hint: 'Base clients active',
      icon: Users,
      accent: 'text-primary',
      iconWrap: 'bg-primary/10 text-primary',
    },
    {
      label: 'Clients à risque',
      value: `${stats.atRiskPct}%`,
      hint: `${stats.atRiskCount} clients à risque élevé`,
      icon: AlertTriangle,
      accent: 'text-danger',
      iconWrap: 'bg-danger/10 text-danger',
    },
    {
      label: 'Taux de churn moyen',
      value: `${stats.avgChurnRate}%`,
      hint: 'Prédit sur 12 mois',
      icon: TrendingDown,
      accent: 'text-warning',
      iconWrap: 'bg-warning/10 text-warning',
    },
    {
      label: 'Score de risque moyen',
      value: `${stats.avgRiskScore}`,
      hint: 'Sur une échelle de 0 à 100',
      icon: Gauge,
      accent: 'text-primary',
      iconWrap: 'bg-primary/10 text-primary',
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((kpi) => {
        const Icon = kpi.icon
        return (
          <Card key={kpi.label} className="overflow-hidden">
            <CardContent className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-muted-foreground">
                  {kpi.label}
                </p>
                <p
                  className={cn(
                    'mt-2 text-3xl font-semibold tracking-tight tabular-nums',
                    kpi.accent,
                  )}
                >
                  {kpi.value}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{kpi.hint}</p>
              </div>
              <span
                className={cn(
                  'flex size-10 shrink-0 items-center justify-center rounded-xl',
                  kpi.iconWrap,
                )}
              >
                <Icon className="size-5" />
              </span>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
