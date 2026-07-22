'use client'

import { Loader2, ShieldCheck } from 'lucide-react'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, type ReactNode } from 'react'
import { useAuth } from '@/lib/auth'

const PAGES_PUBLIQUES = ['/login', '/signup']

/** Redirige vers /login tant qu'aucune session valide n'existe. */
export function AuthGate({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const pathname = usePathname()
  const router = useRouter()
  const pagePublique = PAGES_PUBLIQUES.includes(pathname)

  useEffect(() => {
    if (status === 'unauthenticated' && !pagePublique) router.replace('/login')
    if (status === 'authenticated' && pagePublique) router.replace('/')
  }, [status, pagePublique, router])

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

  return <>{children}</>
}
