'use client'

import { Loader2, ShieldCheck } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
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
import { PasswordInput } from '@/components/ui/password-input'
import { useAuth } from '@/lib/auth'

export default function SignupPage() {
  const { signup } = useAuth()
  const router = useRouter()
  const [organisationNom, setOrganisationNom] = useState('')
  const [nomComplet, setNomComplet] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const soumettre = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!organisationNom.trim() || !username.trim() || !email.trim() || !password || envoi) return
    setEnvoi(true)
    try {
      await signup(organisationNom.trim(), username.trim(), email.trim(), password, nomComplet.trim())
      router.replace('/')
    } catch (err) {
      toast.error('Inscription impossible', {
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
          <CardDescription>
            Créez votre organisation et votre compte administrateur.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={soumettre}>
            <div>
              <Label className="mb-1.5 block text-xs">Nom de l&apos;organisation</Label>
              <Input
                autoFocus
                value={organisationNom}
                onChange={(e) => setOrganisationNom(e.target.value)}
                placeholder="Acme Corp"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Votre nom complet</Label>
              <Input
                value={nomComplet}
                onChange={(e) => setNomComplet(e.target.value)}
                autoComplete="name"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Identifiant</Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Email</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Mot de passe</Label>
              <PasswordInput
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={envoi}>
              {envoi ? <Loader2 className="size-4 animate-spin" /> : null}
              Créer l&apos;organisation
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Déjà un compte ?{' '}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Se connecter
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
