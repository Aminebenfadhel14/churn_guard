'use client'

import { KeyRound, Loader2, LogOut } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { PasswordInput } from '@/components/ui/password-input'
import { useAuth } from '@/lib/auth'

const LONGUEUR_MIN = 8

/**
 * Changement de mot de passe forcé à la première connexion : affiché tant que
 * le compte a un mot de passe temporaire (créé/réinitialisé par un admin). La
 * redirection vers cette page — et le retour vers l'app une fois le mot de
 * passe changé — est pilotée par AuthGate.
 */
export default function ChangePasswordPage() {
  const { user, apiFetch, refreshMe, logout } = useAuth()
  const [nouveauMotDePasse, setNouveauMotDePasse] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const soumettre = async (e: React.FormEvent) => {
    e.preventDefault()
    if (envoi) return
    if (nouveauMotDePasse.length < LONGUEUR_MIN) {
      toast.error('Mot de passe trop court', {
        description: `Choisissez au moins ${LONGUEUR_MIN} caractères.`,
      })
      return
    }
    if (nouveauMotDePasse !== confirmation) {
      toast.error('Les mots de passe ne correspondent pas.')
      return
    }
    setEnvoi(true)
    try {
      // L'utilisateur vient de prouver le mot de passe temporaire à la connexion :
      // cet endpoint ne redemande pas l'ancien mot de passe.
      const rep = await apiFetch('/auth/change-initial-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: nouveauMotDePasse }),
      })
      const d = await rep.json().catch(() => ({}))
      if (!rep.ok) throw new Error(d.detail ?? 'Impossible de changer le mot de passe.')
      // Le flag must_change_password passe à false : AuthGate laisse alors
      // entrer dans l'application.
      await refreshMe()
      toast.success('Mot de passe mis à jour', {
        description: 'Bienvenue sur ChurnGuard.',
      })
    } catch (err) {
      toast.error('Échec du changement', {
        description: err instanceof Error ? err.message : 'Erreur inconnue.',
      })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <span className="mb-2 flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <KeyRound className="size-5" />
          </span>
          <CardTitle className="text-xl">Changez votre mot de passe</CardTitle>
          <CardDescription>
            Votre compte utilise un mot de passe temporaire. Définissez un nouveau mot de passe pour
            accéder à la plateforme.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={soumettre}>
            <div>
              <Label className="mb-1.5 block text-xs">Nouveau mot de passe</Label>
              <PasswordInput
                autoFocus
                value={nouveauMotDePasse}
                onChange={(e) => setNouveauMotDePasse(e.target.value)}
                autoComplete="new-password"
                placeholder={`Au moins ${LONGUEUR_MIN} caractères`}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Confirmer le nouveau mot de passe</Label>
              <PasswordInput
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={envoi}>
              {envoi ? <Loader2 className="size-4 animate-spin" /> : null}
              Enregistrer et continuer
            </Button>
          </form>
          <button
            type="button"
            onClick={logout}
            className="mt-4 flex w-full items-center justify-center gap-1.5 text-center text-sm text-muted-foreground hover:text-foreground"
          >
            <LogOut className="size-3.5" />
            {user?.email ? `Se déconnecter (${user.email})` : 'Se déconnecter'}
          </button>
        </CardContent>
      </Card>
    </div>
  )
}
