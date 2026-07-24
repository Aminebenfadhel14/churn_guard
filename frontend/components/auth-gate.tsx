'use client'

import { Loader2, ShieldCheck } from 'lucide-react'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, type ReactNode } from 'react'
import { useAuth } from '@/lib/auth'

const PAGES_PUBLIQUES = ['/login', '/signup']
const PAGE_CHANGEMENT = '/change-password'

/** Redirige vers /login tant qu'aucune session valide n'existe, et vers
 * /change-password tant que l'utilisateur doit remplacer un mot de passe
 * temporaire (compte créé/réinitialisé par un admin). */
export function AuthGate({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  const pathname = usePathname()
  const router = useRouter()
  const pagePublique = PAGES_PUBLIQUES.includes(pathname)
  const doitChangerMotDePasse = status === 'authenticated' && !!user?.must_change_password

  useEffect(() => {
    if (status === 'unauthenticated' && !pagePublique) router.replace('/login')
    if (status === 'authenticated' && pagePublique) router.replace('/')
    // Mot de passe temporaire : tout est verrouillé sauf la page de changement.
    if (doitChangerMotDePasse && pathname !== PAGE_CHANGEMENT) router.replace(PAGE_CHANGEMENT)
    // Une fois le mot de passe changé, on ne reste pas bloqué sur cette page.
    if (status === 'authenticated' && !doitChangerMotDePasse && pathname === PAGE_CHANGEMENT)
      router.replace('/')
  }, [status, pagePublique, doitChangerMotDePasse, pathname, router])

  if (status === 'loading') {
    return (
      <div className="flex h-svh flex-col items-center justify-center gap-3 text-muted-foreground">
        <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <ShieldCheck className="size-6" />
        </span>
        <Loader2 className="size-5 animate-spin" />
      </div>
    )
  }

  // Redirection en cours : on n'affiche pas le contenu protégé avant qu'elle n'ait lieu.
  if (status === 'unauthenticated' && !pagePublique) return null
  // Mot de passe temporaire : on masque tout sauf la page de changement.
  if (doitChangerMotDePasse && pathname !== PAGE_CHANGEMENT) return null

  return <>{children}</>
}
