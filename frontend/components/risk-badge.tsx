import { cn } from '@/lib/utils'
import { riskLevel, RISK_LABEL } from '@/lib/mock-data'

const STYLES: Record<string, string> = {
  faible: 'bg-success/15 text-success border-success/30',
  moyen: 'bg-warning/15 text-warning border-warning/30',
  eleve: 'bg-danger/15 text-danger border-danger/30',
}

export function RiskBadge({
  score,
  className,
  showScore = true,
}: {
  score: number
  className?: string
  showScore?: boolean
}) {
  const level = riskLevel(score)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
        STYLES[level],
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {RISK_LABEL[level]}
      {showScore && <span className="tabular-nums opacity-80">· {score}</span>}
    </span>
  )
}
