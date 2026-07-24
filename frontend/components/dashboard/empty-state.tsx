import {
  ArrowRight,
  BarChart3,
  BookOpen,
  LayoutDashboard,
  LineChart,
  Sparkles,
  UploadCloud,
  type LucideIcon,
} from 'lucide-react'
import Link from 'next/link'
import { buttonVariants } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface Etape {
  titre: string
  description: string
  icon: LucideIcon
}

const ETAPES: Etape[] = [
  {
    titre: 'Importez',
    description: 'Déposez un fichier CSV, Excel ou Parquet. Le schéma est détecté automatiquement.',
    icon: UploadCloud,
  },
  {
    titre: 'Entraînez',
    description: 'La plateforme compare plusieurs modèles et sélectionne le meilleur pour vous.',
    icon: Sparkles,
  },
  {
    titre: 'Agissez',
    description: 'Visualisez les clients à risque et obtenez des recommandations de rétention.',
    icon: LineChart,
  },
]

/**
 * État vide « onboarding » du tableau de bord : affiché à un opérateur qui n'a
 * pas encore importé de dataset (le backend renvoie `{ empty: true }`). Guide
 * l'utilisateur au lieu de laisser un écran vide ou une erreur.
 */
export function DashboardOnboarding() {
  return (
    <div className="space-y-6">
      {/* 1. Carte héro */}
      <Card className="overflow-hidden border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-transparent">
        <CardContent className="flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:p-8">
          <span className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
            <LayoutDashboard className="size-7" />
          </span>
          <div className="flex-1">
            <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
              Bienvenue sur ChurnGuard
            </h2>
            <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Importez votre premier dataset pour découvrir vos clients à risque, des scores de
              churn et des recommandations de rétention personnalisées. Votre tableau de bord se
              construira automatiquement.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Link href="/upload" className={cn(buttonVariants(), 'gap-2')}>
                <UploadCloud className="size-4" />
                Importer un dataset
              </Link>
              <Link
                href="/docs"
                className={cn(buttonVariants({ variant: 'outline' }), 'gap-2')}
              >
                <BookOpen className="size-4" />
                Voir la documentation
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 2. Guide 3 étapes */}
      <div className="grid gap-4 sm:grid-cols-3">
        {ETAPES.map((etape, i) => {
          const Icon = etape.icon
          return (
            <Card key={etape.titre}>
              <CardContent className="p-5">
                <div className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary tabular-nums">
                    {i + 1}
                  </span>
                  <span className="flex size-9 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                    <Icon className="size-4" />
                  </span>
                </div>
                <h3 className="mt-3 font-medium">{etape.titre}</h3>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {etape.description}
                </p>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* 3. Aperçu grisé (décoratif) du futur tableau de bord */}
      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Aperçu de votre futur tableau de bord
        </p>
        <div
          aria-hidden
          className="pointer-events-none select-none space-y-4 opacity-50"
        >
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            {[
              { label: 'Clients totaux', valeur: '—', icon: LayoutDashboard },
              { label: 'Clients à risque', valeur: '—', icon: BarChart3 },
              { label: 'Taux de churn moyen', valeur: '—', icon: LineChart },
              { label: 'Score de risque moyen', valeur: '—', icon: Sparkles },
            ].map((kpi) => {
              const Icon = kpi.icon
              return (
                <Card key={kpi.label} className="overflow-hidden">
                  <CardContent className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-muted-foreground">{kpi.label}</p>
                      <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-muted-foreground/60">
                        {kpi.valeur}
                      </p>
                      <div className="mt-2 h-2 w-16 rounded-full bg-muted" />
                    </div>
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground/50">
                      <Icon className="size-5" />
                    </span>
                  </CardContent>
                </Card>
              )
            })}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {[0, 1].map((k) => (
              <Card key={k}>
                <CardContent className="p-5">
                  <div className="mb-4 h-3 w-40 rounded-full bg-muted" />
                  <div className="flex h-40 items-end gap-2">
                    {[35, 60, 45, 80, 55, 70, 40, 65].map((h, idx) => (
                      <div
                        key={idx}
                        className="flex-1 rounded-t bg-primary/20"
                        style={{ height: `${h}%` }}
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>

      {/* Rappel discret du CTA sous l'aperçu */}
      <div className="flex justify-center">
        <Link
          href="/upload"
          className={cn(buttonVariants({ variant: 'ghost' }), 'gap-1.5 text-primary')}
        >
          Commencer maintenant
          <ArrowRight className="size-4" />
        </Link>
      </div>
    </div>
  )
}
