'use client'

import { Loader2, MailCheck, ShieldCheck } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
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

const DELAI_RENVOI_SECONDES = 60

export default function LoginPage() {
  const { login, verifyOtp, resendOtp } = useAuth()
  const [etape, setEtape] = useState<'identifiants' | 'otp'>('identifiants')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [challengeToken, setChallengeToken] = useState('')
  const [emailMasque, setEmailMasque] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [renvoiEnvoi, setRenvoiEnvoi] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  const soumettreIdentifiants = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password || envoi) return
    setEnvoi(true)
    try {
      const resultat = await login(username.trim(), password)
      if (resultat.otpRequired) {
        setChallengeToken(resultat.challengeToken)
        setEmailMasque(resultat.emailMasque)
        setEtape('otp')
        setCooldown(DELAI_RENVOI_SECONDES)
      }
      // Sinon, AuthGate redirige automatiquement vers "/" une fois authentifié.
    } catch (err) {
      toast.error('Connexion refusée', {
        description: err instanceof Error ? err.message : 'Erreur inconnue.',
      })
    } finally {
      setEnvoi(false)
    }
  }

  const soumettreCode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (code.trim().length === 0 || envoi) return
    setEnvoi(true)
    try {
      await verifyOtp(challengeToken, code.trim())
      // AuthGate redirige automatiquement vers "/" une fois authentifié.
    } catch (err) {
      toast.error('Vérification échouée', {
        description: err instanceof Error ? err.message : 'Erreur inconnue.',
      })
    } finally {
      setEnvoi(false)
    }
  }

  const renvoyerCode = async () => {
    if (cooldown > 0 || renvoiEnvoi) return
    setRenvoiEnvoi(true)
    try {
      await resendOtp(challengeToken)
      toast.success('Nouveau code envoyé.')
      setCooldown(DELAI_RENVOI_SECONDES)
    } catch (err) {
      toast.error('Impossible de renvoyer le code', {
        description: err instanceof Error ? err.message : 'Erreur inconnue.',
      })
    } finally {
      setRenvoiEnvoi(false)
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <span className="mb-2 flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            {etape === 'identifiants' ? <ShieldCheck className="size-5" /> : <MailCheck className="size-5" />}
          </span>
          <CardTitle className="text-xl">
            Churn<span className="text-primary">Guard</span>
          </CardTitle>
          <CardDescription>
            {etape === 'identifiants'
              ? 'Connectez-vous pour accéder à la plateforme.'
              : `Code envoyé à ${emailMasque}`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {etape === 'identifiants' ? (
            <>
              <form className="space-y-4" onSubmit={soumettreIdentifiants}>
                <div>
                  <Label className="mb-1.5 block text-xs">Email</Label>
                  <Input
                    autoFocus
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="email"
                  />
                </div>
                <div>
                  <Label className="mb-1.5 block text-xs">Mot de passe</Label>
                  <PasswordInput
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
              <p className="mt-4 text-center text-sm text-muted-foreground">
                Nouvelle organisation ?{' '}
                <Link href="/signup" className="font-medium text-primary hover:underline">
                  Créer un compte
                </Link>
              </p>
            </>
          ) : (
            <form className="space-y-4" onSubmit={soumettreCode}>
              <div>
                <Label className="mb-1.5 block text-xs">Code de vérification</Label>
                <Input
                  autoFocus
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="000000"
                  className="text-center text-lg tracking-[0.5em]"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                />
              </div>
              <Button type="submit" className="w-full" disabled={envoi}>
                {envoi ? <Loader2 className="size-4 animate-spin" /> : null}
                Vérifier
              </Button>
              <button
                type="button"
                onClick={renvoyerCode}
                disabled={cooldown > 0 || renvoiEnvoi}
                className="w-full text-center text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
              >
                {cooldown > 0 ? `Renvoyer le code (${cooldown}s)` : 'Renvoyer le code'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setEtape('identifiants')
                  setCode('')
                }}
                className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
              >
                Retour à la connexion
              </button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
