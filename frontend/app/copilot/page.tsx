'use client'

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Copy,
  Loader2,
  MessageSquare,
  Send,
  User,
  Zap,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { RiskScoreCard } from '@/components/client/risk-score-card'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000'

interface Feature {
  nom: string
  type: 'numerique' | 'categoriel' | 'booleen' | 'date' | 'texte'
  valeurs: (string | number)[] | null
  min: number | null
  max: number | null
}
interface Schema {
  cible: string | null
  features: Feature[]
}
interface Message {
  role: 'user' | 'assistant'
  content: string
}
interface Facteur {
  feature: string
  label: string
  contribution: number
}
interface Action {
  action?: string
  detail?: string
}
interface ExpressResult {
  risk_score: number
  risk_level: string
  facteurs: Facteur[]
  recommendations: Action[]
  email_alerte?: { subject?: string; body?: string }
  escalade: boolean
  decision: string
  synthese: string
  source_synthese: string
}

const SUGGESTIONS = [
  'Traite ce client de A à Z.',
  'Quelle est la meilleure action pour réduire son risque ?',
  'Explique pourquoi il est à risque.',
  'Donne-moi le résumé du dashboard.',
]

function valeurInitiale(f: Feature): string {
  if (f.type === 'categoriel' || f.type === 'booleen') {
    return f.valeurs && f.valeurs.length ? String(f.valeurs[0]) : ''
  }
  if (f.type === 'numerique') return String(f.min ?? 0)
  return ''
}

export default function CopilotPage() {
  const [schema, setSchema] = useState<Schema | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [erreurSchema, setErreurSchema] = useState<string | null>(null)

  const [mode, setMode] = useState<'assistant' | 'express'>('assistant')

  // Chat
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const finRef = useRef<HTMLDivElement>(null)

  // Analyse express
  const [running, setRunning] = useState(false)
  const [erreurExpress, setErreurExpress] = useState<string | null>(null)
  const [res, setRes] = useState<ExpressResult | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const rep = await fetch(`${API_URL}/schema`)
        if (!rep.ok)
          throw new Error('Aucun modèle entraîné (lance un entraînement depuis Upload).')
        const s: Schema = await rep.json()
        setSchema(s)
        const init: Record<string, string> = {}
        s.features.forEach((f) => (init[f.nom] = valeurInitiale(f)))
        setValues(init)
      } catch (e) {
        setErreurSchema(
          e instanceof Error && e.message.includes('fetch')
            ? "Impossible de joindre l'API (uvicorn app.main:app)."
            : (e as Error).message,
        )
      }
    })()
  }, [])

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const set = (nom: string, v: string) =>
    setValues((prev) => ({ ...prev, [nom]: v }))

  const envoyer = async (texte?: string) => {
    const q = (texte ?? input).trim()
    if (!q || sending) return
    setMode('assistant')
    const nouveaux: Message[] = [...messages, { role: 'user', content: q }]
    setMessages(nouveaux)
    setInput('')
    setSending(true)
    try {
      const rep = await fetch(`${API_URL}/copilot/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: nouveaux, client: values }),
      })
      const d = await rep.json().catch(() => ({}))
      if (!rep.ok) throw new Error(d.detail ?? `Erreur ${rep.status}`)
      setMessages((m) => [...m, { role: 'assistant', content: d.reply ?? '(vide)' }])
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content:
            '⚠️ ' +
            (e instanceof Error && e.message.includes('fetch')
              ? 'API injoignable (uvicorn app.main:app).'
              : (e as Error).message),
        },
      ])
    } finally {
      setSending(false)
    }
  }

  const lancerExpress = async () => {
    setRunning(true)
    setErreurExpress(null)
    setRes(null)
    try {
      const rep = await fetch(`${API_URL}/copilot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      })
      const d = await rep.json().catch(() => ({}))
      if (!rep.ok) throw new Error(d.detail ?? `Erreur ${rep.status}`)
      setRes(d)
    } catch (e) {
      setErreurExpress(
        e instanceof Error && e.message.includes('fetch')
          ? "Impossible de joindre l'API (uvicorn app.main:app)."
          : (e as Error).message,
      )
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Bot className="size-6 text-primary" /> Retention Copilot
        </h1>
        <p className="mt-1 text-muted-foreground">
          Un assistant qui raisonne sur un client : discute avec lui, ou lance
          une analyse complète en un clic.
        </p>
      </div>

      {erreurSchema && (
        <Card className="mb-4 border-danger/40">
          <CardContent className="flex items-start gap-2 pt-6 text-sm text-danger">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span>{erreurSchema}</span>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Client partagé */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Client courant</CardTitle>
            <CardDescription>Partagé par les deux modes.</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[440px] space-y-3 overflow-y-auto">
            {schema?.features.map((f) => (
              <div key={f.nom}>
                <Label className="mb-1 block text-xs">{f.nom}</Label>
                {f.type === 'categoriel' || f.type === 'booleen' ? (
                  <Select value={values[f.nom] ?? ''} onValueChange={(v) => set(f.nom, v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(f.valeurs ?? []).map((v) => (
                        <SelectItem key={String(v)} value={String(v)}>{String(v)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    type={f.type === 'numerique' ? 'number' : 'text'}
                    value={values[f.nom] ?? ''}
                    onChange={(e) => set(f.nom, e.target.value)}
                  />
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Panneau assistant / express */}
        <div className="lg:col-span-2">
          {/* Sélecteur de mode */}
          <div className="mb-3 inline-flex rounded-lg border border-border bg-muted/40 p-1">
            <button
              type="button"
              onClick={() => setMode('assistant')}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                mode === 'assistant'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <MessageSquare className="size-4" /> Assistant
            </button>
            <button
              type="button"
              onClick={() => setMode('express')}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                mode === 'express'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Zap className="size-4" /> Analyse express
            </button>
          </div>

          {mode === 'assistant' ? (
            <Card className="flex h-[520px] flex-col">
              <CardContent className="flex flex-1 flex-col gap-3 overflow-y-auto pt-6">
                {messages.length === 0 && (
                  <div className="m-auto max-w-sm text-center text-sm text-muted-foreground">
                    <Bot className="mx-auto mb-2 size-8 text-primary/60" />
                    Pose une question sur ce client.
                    <div className="mt-4 flex flex-wrap justify-center gap-2">
                      {SUGGESTIONS.map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => envoyer(s)}
                          className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={cn('flex gap-2', m.role === 'user' && 'flex-row-reverse')}>
                    <span
                      className={cn(
                        'flex size-7 shrink-0 items-center justify-center rounded-full',
                        m.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-primary/10 text-primary',
                      )}
                    >
                      {m.role === 'user' ? <User className="size-4" /> : <Bot className="size-4" />}
                    </span>
                    <div
                      className={cn(
                        'max-w-[80%] whitespace-pre-line rounded-2xl px-3 py-2 text-sm',
                        m.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted',
                      )}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
                {sending && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Bot className="size-4 text-primary" />
                    <Loader2 className="size-4 animate-spin" /> L&apos;assistant réfléchit…
                  </div>
                )}
                <div ref={finRef} />
              </CardContent>
              <div className="flex items-center gap-2 border-t border-border p-3">
                <Input
                  placeholder="Écris ta demande…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void envoyer()
                    }
                  }}
                  disabled={sending}
                />
                <Button onClick={() => envoyer()} disabled={sending || !input.trim()}>
                  <Send className="size-4" />
                </Button>
              </div>
            </Card>
          ) : (
            <div className="space-y-4">
              <Button className="w-full" onClick={lancerExpress} disabled={running}>
                {running ? (
                  <><Loader2 className="size-4 animate-spin" /> Analyse en cours…</>
                ) : (
                  <><Zap className="size-4" /> Lancer l&apos;analyse complète</>
                )}
              </Button>

              {erreurExpress && (
                <Card className="border-danger/40">
                  <CardContent className="flex items-start gap-2 pt-6 text-sm text-danger">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                    <span>{erreurExpress}</span>
                  </CardContent>
                </Card>
              )}

              {res && (
                <>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <RiskScoreCard score={res.risk_score} />
                    <Card className={res.escalade ? 'border-danger/40' : undefined}>
                      <CardContent className="flex h-full items-center gap-2 pt-6 text-sm font-medium">
                        {res.escalade ? (
                          <AlertTriangle className="size-4 text-danger" />
                        ) : (
                          <CheckCircle2 className="size-4 text-success" />
                        )}
                        {res.decision}
                      </CardContent>
                    </Card>
                  </div>

                  <Card className="border-primary/30">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Bot className="size-4 text-primary" /> Synthèse
                        {res.source_synthese === 'llm' ? (
                          <span className="ml-auto rounded border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-[11px] font-normal text-primary">
                            RAG · IA + playbooks
                          </span>
                        ) : (
                          <span className="ml-auto rounded border border-warning/40 bg-warning/10 px-1.5 py-0.5 text-[11px] font-normal text-warning">
                            Moteur de règles (secours)
                          </span>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="whitespace-pre-line text-sm leading-relaxed">{res.synthese}</p>
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-3"
                        onClick={() =>
                          envoyer('Quelle est la meilleure action de rétention pour ce client, et pourquoi ?')
                        }
                      >
                        <MessageSquare className="size-4" /> En discuter avec l&apos;assistant
                      </Button>
                    </CardContent>
                  </Card>

                  {res.email_alerte?.body && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">Email d&apos;alerte (prêt)</CardTitle>
                        <CardDescription>Rien n&apos;est envoyé : à vous de valider.</CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <div className="text-sm font-medium">{res.email_alerte.subject}</div>
                        <textarea
                          readOnly
                          rows={9}
                          value={res.email_alerte.body}
                          className="w-full rounded-lg border border-border bg-muted/30 p-2.5 text-xs leading-relaxed"
                        />
                        <Button
                          variant="outline"
                          onClick={() => {
                            navigator.clipboard
                              .writeText(`${res.email_alerte?.subject}\n\n${res.email_alerte?.body}`)
                              .then(() => toast.success('Email copié'))
                              .catch(() => toast.error('Copie impossible'))
                          }}
                        >
                          <Copy className="size-4" /> Copier l&apos;email
                        </Button>
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
