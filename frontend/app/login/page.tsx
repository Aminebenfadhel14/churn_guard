'use client'

import { Loader2, ShieldCheck } from 'lucide-react'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/lib/auth'

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const soumettre = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password || envoi) return
    setEnvoi(true)
    try {
      await login(username.trim(), password)
      // AuthGate redirige automatiquement vers "/" une fois authentifié.
    } catch (err) {
      toast.error('Connexion refusée', {
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
            <ShieldCheck className="size-5" />
          </span>
          <CardTitle className="text-xl">
            Churn<span className="text-primary">Guard</span>
          </CardTitle>
          <CardDescription>Connectez-vous pour accéder à la plateforme.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={soumettre}>
            <div>
              <Label className="mb-1.5 block text-xs">Identifiant</Label>
              <Input
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Mot de passe</Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={envoi}>
              {envoi ? <Loader2 className="size-4 animate-spin" /> : null}
              Se connecter
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
