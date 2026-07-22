'use client'

import { Layers, Loader2, LogIn, Pencil, ShieldAlert, Trash2, UserPlus, Users } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PasswordInput } from '@/components/ui/password-input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAuth } from '@/lib/auth'

interface Membre {
  username: string
  email: string | null
  nom_complet: string
  role: string
}

interface ModeleEntraine {
  version: string
  label: string
  cible: string | null
  algorithme: string | null
  n_features: number
  date: string | null
  actif: boolean
  username: string | null
  proprietaire: string | null
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

export default function TeamPage() {
  const { user, apiFetch, impersonate } = useAuth()
  const router = useRouter()
  const [membres, setMembres] = useState<Membre[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [connexionEnCours, setConnexionEnCours] = useState<string | null>(null)

  const [nomComplet, setNomComplet] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const [aSupprimer, setASupprimer] = useState<Membre | null>(null)
  const [suppression, setSuppression] = useState(false)

  const [aModifier, setAModifier] = useState<Membre | null>(null)
  const [modifNomComplet, setModifNomComplet] = useState('')
  const [modifEmail, setModifEmail] = useState('')
  const [modifRole, setModifRole] = useState('operateur')
  const [modifPassword, setModifPassword] = useState('')
  const [modification, setModification] = useState(false)

  const [modeles, setModeles] = useState<ModeleEntraine[] | null>(null)
  const [modelesLoading, setModelesLoading] = useState(true)
  const [activationEnCours, setActivationEnCours] = useState<string | null>(null)
  const [aSupprimerModele, setASupprimerModele] = useState<ModeleEntraine | null>(null)
  const [suppressionModele, setSuppressionModele] = useState(false)

  const charger = useCallback(async () => {
    setLoading(true)
    try {
      const rep = await apiFetch('/auth/users')
      if (!rep.ok) throw new Error("Impossible de charger l'équipe.")
      setMembres(await rep.json())
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setLoading(false)
    }
  }, [apiFetch])

  const chargerModeles = useCallback(async () => {
    setModelesLoading(true)
    try {
      const rep = await apiFetch('/models')
      if (!rep.ok) throw new Error('Impossible de charger les modèles.')
      const d = await rep.json()
      setModeles(d.models ?? [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setModelesLoading(false)
    }
  }, [apiFetch])

  const activerModele = async (m: ModeleEntraine) => {
    if (m.actif || activationEnCours) return
    setActivationEnCours(m.version)
    try {
      const rep = await apiFetch('/models/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: m.version }),
      })
      if (!rep.ok) throw new Error(`Erreur ${rep.status}`)
      toast.success('Modèle activé', { description: m.label })
      window.location.reload()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
      setActivationEnCours(null)
    }
  }

  const supprimerModele = async () => {
    if (!aSupprimerModele || suppressionModele) return
    setSuppressionModele(true)
    try {
      const rep = await apiFetch(`/models/${encodeURIComponent(aSupprimerModele.version)}`, {
        method: 'DELETE',
      })
      const d = await rep.json().catch(() => ({}))
      if (!rep.ok) throw new Error(d.detail ?? 'Impossible de supprimer ce modèle.')
      toast.success('Modèle supprimé')
      setModeles((prev) => prev?.filter((m) => m.version !== aSupprimerModele.version) ?? null)
      setASupprimerModele(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setSuppressionModele(false)
    }
  }

  useEffect(() => {
    if (user?.role === 'admin') {
      charger()
      chargerModeles()
    }
  }, [user, charger, chargerModeles])

  const ajouterEmploye = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password || envoi) return
    setEnvoi(true)
    try {
      const rep = await apiFetch('/auth/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim(),
          password,
          nom_complet: nomComplet.trim(),
        }),
      })
      const d = await rep.json().catch(() => ({}))
      if (!rep.ok) throw new Error(d.detail ?? 'Impossible de créer le compte.')
      toast.success(`Compte créé : ${d.email}`, {
        description: 'Un email de bienvenue avec les identifiants a été envoyé.',
      })
      setNomComplet('')
      setEmail('')
      setPassword('')
      charger()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setEnvoi(false)
    }
  }

  const supprimerMembre = async () => {
    if (!aSupprimer || suppression) return
    setSuppression(true)
    try {
      const rep = await apiFetch(`/auth/users/${encodeURIComponent(aSupprimer.username)}`, {
        method: 'DELETE',
      })
      const d = await rep.json().catch(() => ({}))
      if (!rep.ok) throw new Error(d.detail ?? 'Impossible de supprimer ce compte.')
      toast.success(`Compte supprimé : ${aSupprimer.email ?? aSupprimer.username}`)
      setASupprimer(null)
      charger()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setSuppression(false)
    }
  }

  const seConnecterEnTantQue = async (m: Membre) => {
    if (connexionEnCours) return
    setConnexionEnCours(m.username)
    try {
      await impersonate(m.username)
      toast.success(`Connecté en tant que ${m.nom_complet}`)
      router.push('/')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setConnexionEnCours(null)
    }
  }

  const ouvrirModification = (m: Membre) => {
    setAModifier(m)
    setModifNomComplet(m.nom_complet)
    setModifEmail(m.email ?? '')
    setModifRole(m.role)
    setModifPassword('')
  }

  const modifierMembre = async () => {
    if (!aModifier || modification) return
    setModification(true)
    try {
      const rep = await apiFetch(`/auth/users/${encodeURIComponent(aModifier.username)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nom_complet: modifNomComplet.trim(),
          role: modifRole,
          email: modifEmail.trim(),
          ...(modifPassword ? { password: modifPassword } : {}),
        }),
      })
      const d = await rep.json().catch(() => ({}))
      if (!rep.ok) throw new Error(d.detail ?? 'Impossible de modifier ce compte.')
      toast.success(`Compte modifié : ${d.email ?? d.username}`)
      setAModifier(null)
      charger()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur inconnue.')
    } finally {
      setModification(false)
    }
  }

  if (user && user.role !== 'admin') {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <ShieldAlert className="mx-auto mb-3 size-10 text-muted-foreground" />
        <h1 className="text-lg font-semibold">Accès réservé aux administrateurs</h1>
        <p className="mt-1 text-muted-foreground">
          Seul un compte administrateur peut gérer les membres de l&apos;équipe.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Users className="size-6 text-primary" /> Équipe
        </h1>
        <p className="mt-1 text-muted-foreground">
          Gérez les comptes de votre organisation.
        </p>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <UserPlus className="size-4" /> Ajouter un employé
          </CardTitle>
          <CardDescription>
            Le compte créé a le rôle &quot;opérateur&quot; et rejoint votre organisation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 sm:grid-cols-3" onSubmit={ajouterEmploye}>
            <div>
              <Label className="mb-1.5 block text-xs">Nom complet</Label>
              <Input value={nomComplet} onChange={(e) => setNomComplet(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Mot de passe</Label>
              <PasswordInput
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={envoi} className="sm:col-span-3">
              {envoi ? <Loader2 className="size-4 animate-spin" /> : null}
              Créer le compte
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Membres</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nom</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Rôle</TableHead>
                  <TableHead className="w-0" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {membres?.map((m) => (
                  <TableRow key={m.username}>
                    <TableCell>{m.nom_complet}</TableCell>
                    <TableCell className="text-muted-foreground">{m.email ?? '—'}</TableCell>
                    <TableCell className="capitalize">{m.role}</TableCell>
                    <TableCell className="flex justify-end gap-1 text-right">
                      {m.role !== 'admin' && m.username !== user?.username && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => seConnecterEnTantQue(m)}
                          disabled={connexionEnCours === m.username}
                          aria-label={`Se connecter en tant que ${m.username}`}
                          title="Se connecter en tant que cet utilisateur"
                        >
                          {connexionEnCours === m.username ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <LogIn className="size-4" />
                          )}
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => ouvrirModification(m)}
                        aria-label={`Modifier ${m.username}`}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      {m.username !== user?.username && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => setASupprimer(m)}
                          aria-label={`Supprimer ${m.username}`}
                        >
                          <Trash2 className="size-4 text-destructive" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Layers className="size-4" /> Modèles entraînés
          </CardTitle>
          <CardDescription>
            Tous les datasets entraînés par l&apos;équipe, tous utilisateurs confondus.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {modelesLoading ? (
            <div className="flex justify-center py-8 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : !modeles || modeles.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              Aucun modèle entraîné pour l&apos;instant.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Dataset</TableHead>
                    <TableHead>Entraîné par</TableHead>
                    <TableHead>Cible</TableHead>
                    <TableHead>Algorithme</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead className="w-0" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {modeles.map((m) => (
                    <TableRow key={m.version}>
                      <TableCell className="font-medium">{m.label}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {m.proprietaire ?? m.username ?? 'Utilisateur inconnu'}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{m.cible ?? '—'}</TableCell>
                      <TableCell className="text-muted-foreground">{m.algorithme ?? '—'}</TableCell>
                      <TableCell className="text-muted-foreground">{formatDate(m.date)}</TableCell>
                      <TableCell>
                        {m.actif ? (
                          <Badge>Actif</Badge>
                        ) : (
                          <Badge variant="outline">Inactif</Badge>
                        )}
                      </TableCell>
                      <TableCell className="flex justify-end gap-1 text-right">
                        {!m.actif && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => activerModele(m)}
                            disabled={activationEnCours === m.version}
                          >
                            {activationEnCours === m.version ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              'Activer'
                            )}
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => setASupprimerModele(m)}
                          disabled={m.actif}
                          title={m.actif ? "Désactivez-le d'abord pour le supprimer" : undefined}
                          aria-label={`Supprimer ${m.label}`}
                        >
                          <Trash2 className="size-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={!!aSupprimerModele}
        onOpenChange={(open) => !open && setASupprimerModele(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer ce modèle ?</DialogTitle>
            <DialogDescription>
              Le modèle <strong>{aSupprimerModele?.label}</strong>
              {aSupprimerModele?.proprietaire ? ` (${aSupprimerModele.proprietaire})` : ''} sera
              définitivement supprimé. Cette action est irréversible.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setASupprimerModele(null)}
              disabled={suppressionModele}
            >
              Annuler
            </Button>
            <Button variant="destructive" onClick={supprimerModele} disabled={suppressionModele}>
              {suppressionModele ? <Loader2 className="size-4 animate-spin" /> : null}
              Supprimer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!aSupprimer} onOpenChange={(open) => !open && setASupprimer(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer ce compte ?</DialogTitle>
            <DialogDescription>
              Le compte <strong>{aSupprimer?.email ?? aSupprimer?.username}</strong> (
              {aSupprimer?.nom_complet}) sera définitivement supprimé. Cette action est
              irréversible.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setASupprimer(null)} disabled={suppression}>
              Annuler
            </Button>
            <Button variant="destructive" onClick={supprimerMembre} disabled={suppression}>
              {suppression ? <Loader2 className="size-4 animate-spin" /> : null}
              Supprimer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!aModifier} onOpenChange={(open) => !open && setAModifier(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Modifier {aModifier?.email ?? aModifier?.username}</DialogTitle>
            <DialogDescription>
              Laisse le mot de passe vide pour ne pas le changer.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div>
              <Label className="mb-1.5 block text-xs">Nom complet</Label>
              <Input value={modifNomComplet} onChange={(e) => setModifNomComplet(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Email</Label>
              <Input type="email" value={modifEmail} onChange={(e) => setModifEmail(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Rôle</Label>
              <Select
                value={modifRole}
                onValueChange={setModifRole}
                disabled={aModifier?.username === user?.username}
              >
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="operateur">Opérateur</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Nouveau mot de passe</Label>
              <PasswordInput
                value={modifPassword}
                onChange={(e) => setModifPassword(e.target.value)}
                placeholder="(inchangé)"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAModifier(null)} disabled={modification}>
              Annuler
            </Button>
            <Button onClick={modifierMembre} disabled={modification}>
              {modification ? <Loader2 className="size-4 animate-spin" /> : null}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
