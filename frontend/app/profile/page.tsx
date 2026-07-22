'use client'

import { User } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/lib/auth'

function initiales(nom: string): string {
  return nom
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((mot) => mot[0]?.toUpperCase())
    .join('')
}

export default function ProfilePage() {
  const { user } = useAuth()

  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <User className="size-6 text-primary" /> Profil
        </h1>
        <p className="mt-1 text-muted-foreground">Informations du compte connecté.</p>
      </div>

      {user && (
        <Card>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <Avatar className="size-12">
              <AvatarFallback className="bg-primary/10 text-primary font-semibold">
                {initiales(user.nom_complet)}
              </AvatarFallback>
            </Avatar>
            <div>
              <CardTitle className="text-base">{user.nom_complet}</CardTitle>
              <CardDescription>@{user.username}</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {user.email && (
              <div className="flex justify-between rounded-lg bg-muted/50 p-2.5">
                <span className="text-muted-foreground">Email</span>
                <span className="font-medium">{user.email}</span>
              </div>
            )}
            <div className="flex justify-between rounded-lg bg-muted/50 p-2.5">
              <span className="text-muted-foreground">Rôle</span>
              <span className="font-medium">{user.role}</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
