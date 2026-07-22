'use client'

import { Building2, KeyRound, Loader2, Monitor, Moon, Settings, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
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

interface InfosOrganisation {
  nom: string
  membres: number
}

export default function SettingsPage() {
  const { user, apiFetch, refreshMe } = useAuth()

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Settings className="size-6 text-primary" /> Paramètres
        </h1>
        <p className="mt-1 text-muted-foreground">Gérez votre compte et vos préférences.</p>
      </div>

      <div className="space-y-6">
        <CompteSection />
        <ApparenceSection />
        {user && <OrganisationSection admin={user.role === 'admin'} apiFetch={apiFetch} />}
      </div>
    </div>
  )

  function CompteSection() {
    const [nomComplet, setNomComplet] = useState(user?.nom_complet ?? '')
    const [email, setEmail] = useState(user?.email ?? '')
    const [motDePasseActuel, setMotDePasseActuel] = useState('')
    const [nouveauMotDePasse, setNouveauMotDePasse] = useState('')
    const [envoi, setEnvoi] = useState(false)

    const emailModifie = email.trim() !== (user?.email ?? '')
    const necessiteMotDePasse = emailModifie || nouveauMotDePasse.length > 0

    const enregistrer = async (e: React.FormEvent) => {
      e.preventDefault()
      if (envoi) return
      if (necessiteMotDePasse && !motDePasseActuel) {
        toast.error('Mot de passe actuel requis', {
          description: 'Nécessaire pour changer votre email ou votre mot de passe.',
        })
        return
      }
      setEnvoi(true)
      try {
        const rep = await apiFetch('/auth/me', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            nom_complet: nomComplet.trim(),
            ...(emailModifie ? { email: email.trim() } : {}),
            ...(nouveauMotDePasse ? { password: nouveauMotDePasse } : {}),
            ...(necessiteMotDePasse ? { mot_de_passe_actuel: motDePasseActuel } : {}),
          }),
        })
        const d = await rep.json().catch(() => ({}))
        if (!rep.ok) throw new Error(d.detail ?? 'Impossible de mettre à jour le compte.')
        await refreshMe()
        setMotDePasseActuel('')
        setNouveauMotDePasse('')
        toast.success('Compte mis à jour')
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
      } finally {
        setEnvoi(false)
      }
    }

    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <KeyRound className="size-4" /> Compte & Sécurité
          </CardTitle>
          <CardDescription>
            Changez votre nom, votre email ou votre mot de passe.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={enregistrer}>
            <div>
              <Label className="mb-1.5 block text-xs">Nom complet</Label>
              <Input value={nomComplet} onChange={(e) => setNomComplet(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Nouveau mot de passe</Label>
              <PasswordInput
                value={nouveauMotDePasse}
                onChange={(e) => setNouveauMotDePasse(e.target.value)}
                placeholder="(inchangé)"
              />
            </div>
            {necessiteMotDePasse && (
              <div>
                <Label className="mb-1.5 block text-xs">Mot de passe actuel (pour confirmer)</Label>
                <PasswordInput
                  value={motDePasseActuel}
                  onChange={(e) => setMotDePasseActuel(e.target.value)}
                />
              </div>
            )}
            <Button type="submit" disabled={envoi}>
              {envoi ? <Loader2 className="size-4 animate-spin" /> : null}
              Enregistrer
            </Button>
          </form>
        </CardContent>
      </Card>
    )
  }
}

function ApparenceSection() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const options: { valeur: string; label: string; icon: typeof Sun }[] = [
    { valeur: 'light', label: 'Clair', icon: Sun },
    { valeur: 'dark', label: 'Sombre', icon: Moon },
    { valeur: 'system', label: 'Système', icon: Monitor },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Apparence</CardTitle>
        <CardDescription>Choisissez le thème de l&apos;interface.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2">
          {options.map(({ valeur, label, icon: Icon }) => (
            <Button
              key={valeur}
              type="button"
              variant={mounted && theme === valeur ? 'default' : 'outline'}
              onClick={() => setTheme(valeur)}
              className="flex-1"
            >
              <Icon className="size-4" /> {label}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function OrganisationSection({
  admin,
  apiFetch,
}: {
  admin: boolean
  apiFetch: (path: string, init?: RequestInit) => Promise<Response>
}) {
  const [infos, setInfos] = useState<InfosOrganisation | null>(null)
  const [nom, setNom] = useState('')
  const [envoi, setEnvoi] = useState(false)

  useEffect(() => {
    apiFetch('/auth/organisation')
      .then((r) => (r.ok ? r.json() : null))
      .then((d: InfosOrganisation | null) => {
        if (!d) return
        setInfos(d)
        setNom(d.nom)
      })
      .catch(() => {})
    // apiFetch change de référence à chaque changement d'identité (nouveau
    // token) : le suivre en dépendance évite d'afficher l'organisation de la
    // session précédente après un changement de compte (impersonation).
  }, [apiFetch])

  const enregistrer = async () => {
    if (envoi || !nom.trim()) return
    setEnvoi(true)
    try {
      const rep = await apiFetch('/auth/organisation', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nom: nom.trim() }),
      })
      const d = await rep.json().catch(() => ({}))
      if (!rep.ok) throw new Error(d.detail ?? "Impossible de renommer l'organisation.")
      setInfos((i) => (i ? { ...i, nom: d.nom } : i))
      toast.success('Organisation renommée')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="size-4" /> Organisation
        </CardTitle>
        <CardDescription>
          {infos ? `${infos.membres} membre${infos.membres > 1 ? 's' : ''}` : '…'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label className="mb-1.5 block text-xs">Nom de l&apos;organisation</Label>
          <Input value={nom} onChange={(e) => setNom(e.target.value)} disabled={!admin} />
        </div>
        {admin && (
          <Button onClick={enregistrer} disabled={envoi}>
            {envoi ? <Loader2 className="size-4 animate-spin" /> : null}
            Enregistrer
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
