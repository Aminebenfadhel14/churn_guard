import { Braces, KeyRound } from 'lucide-react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

interface Endpoint {
  method: 'POST' | 'GET'
  path: string
  title: string
  description: string
  request?: string
  response: string
}

const ENDPOINTS: Endpoint[] = [
  {
    method: 'POST',
    path: '/predict',
    title: 'Prédire le churn',
    description: "Retourne le score de risque d'attrition d'un client (0-100).",
    request: `{
  "CreditScore": 619, "Geography": "France", "Gender": "Female",
  "Age": 42, "Tenure": 2, "Balance": 0.0, "NumOfProducts": 1,
  "HasCrCard": 1, "IsActiveMember": 1, "EstimatedSalary": 101348.88
}`,
    response: `{ "risk_score": 78.4, "prediction": 1, "risk_level": "eleve" }`,
  },
  {
    method: 'POST',
    path: '/explain',
    title: 'Expliquer une prédiction (SHAP)',
    description: 'Retourne les contributions SHAP des variables pour un client.',
    request: `{ "client": { ...mêmes champs que /predict } }`,
    response: `{
  "features": [
    { "feature": "Age", "contribution": 12.3 },
    { "feature": "NumOfProducts", "contribution": -8.1 }
  ]
}`,
  },
  {
    method: 'POST',
    path: '/recommend',
    title: 'Actions de rétention',
    description: 'Renvoie des actions priorisées selon le niveau de risque.',
    request: `{ "client": { ... }, "risk_score": 78.4 }`,
    response: `{
  "recommendations": [
    { "action": "Offre annuelle avec remise", "impact": 18, "priority": "Haute" }
  ]
}`,
  },
  {
    method: 'POST',
    path: '/what-if',
    title: 'Simulation What-if',
    description: 'Recalcule le score après modification de certaines variables.',
    request: `{ "client": { ... }, "overrides": { "NumOfProducts": 2 } }`,
    response: `{ "risk_score": 61.0, "delta": -17.4 }`,
  },
]

const METHOD_STYLE: Record<string, string> = {
  POST: 'bg-primary/15 text-primary',
  GET: 'bg-success/15 text-success',
}

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Documentation API</h1>
        <p className="mt-1 text-muted-foreground">
          Endpoints REST exposés par le backend FastAPI de ChurnGuard.
        </p>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <KeyRound className="size-4 text-primary" /> Authentification
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            Chaque requête doit inclure l&apos;en-tête <code className="rounded bg-muted px-1.5 py-0.5">x-api-key</code>{' '}
            avec la clé définie dans la variable d&apos;environnement du serveur.
          </p>
          <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">
{`curl -X POST "$CHURNGUARD_API_URL/predict" \\
  -H "x-api-key: $CHURNGUARD_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{ ... }'`}
          </pre>
          <p>
            La documentation interactive Swagger est aussi disponible sur{' '}
            <code className="rounded bg-muted px-1.5 py-0.5">/docs</code> côté FastAPI.
          </p>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {ENDPOINTS.map((e) => (
          <Card key={e.path}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <span className={'rounded px-2 py-0.5 text-xs font-semibold ' + METHOD_STYLE[e.method]}>
                  {e.method}
                </span>
                <code className="font-mono">{e.path}</code>
              </CardTitle>
              <CardDescription>{e.description}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {e.request && (
                <div>
                  <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                    <Braces className="size-3.5" /> Requête
                  </div>
                  <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">{e.request}</pre>
                </div>
              )}
              <div>
                <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                  <Braces className="size-3.5" /> Réponse
                </div>
                <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">{e.response}</pre>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
