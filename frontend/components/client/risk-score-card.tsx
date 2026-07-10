import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { riskLevel, RISK_LABEL } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

function color(level: string) {
  return level === 'faible'
    ? 'var(--success)'
    : level === 'moyen'
      ? 'var(--warning)'
      : 'var(--danger)'
}

export function RiskScoreCard({ score }: { score: number }) {
  const level = riskLevel(score)
  const c = color(level)
  const textColor =
    level === 'faible'
      ? 'text-success'
      : level === 'moyen'
        ? 'text-warning'
        : 'text-danger'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Score de risque</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-3">
          <span className={cn('text-5xl font-semibold tabular-nums', textColor)}>
            {score}
          </span>
          <span className="mb-1.5 text-lg text-muted-foreground">/100</span>
          <span
            className={cn(
              'mb-2 ml-auto rounded-full px-3 py-1 text-sm font-medium',
              textColor,
            )}
            style={{ backgroundColor: `color-mix(in oklch, ${c} 15%, transparent)` }}
          >
            Risque {RISK_LABEL[level]}
          </span>
        </div>

        <div
          className="mt-4 h-3 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${score}%`, backgroundColor: c }}
          />
        </div>
        <div className="mt-2 flex justify-between text-xs text-muted-foreground">
          <span>0 — Faible</span>
          <span>30</span>
          <span>70</span>
          <span>100 — Élevé</span>
        </div>
      </CardContent>
    </Card>
  )
}
