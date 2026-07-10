'use client'

import { ChevronRight } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { RiskBadge } from '@/components/risk-badge'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { Client } from '@/lib/types'

export function TopRiskTable({ clients }: { clients: Client[] }) {
  const router = useRouter()

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <div>
          <CardTitle className="text-base">Top 10 clients à risque</CardTitle>
          <CardDescription>
            Priorisez vos actions de rétention.
          </CardDescription>
        </div>
        <Link
          href="/clients?risk=eleve"
          className="text-sm font-medium text-primary hover:underline whitespace-nowrap"
        >
          Voir tout
        </Link>
      </CardHeader>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Client</TableHead>
              <TableHead className="hidden md:table-cell">Segment</TableHead>
              <TableHead className="hidden sm:table-cell">Ancienneté</TableHead>
              <TableHead className="hidden lg:table-cell">Contrat</TableHead>
              <TableHead>Risque</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {clients.map((c) => (
              <TableRow
                key={c.id}
                className="cursor-pointer"
                onClick={() => router.push(`/clients/${c.id}`)}
              >
                <TableCell>
                  <div className="font-medium">{c.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {c.company}
                  </div>
                </TableCell>
                <TableCell className="hidden md:table-cell text-muted-foreground">
                  {c.segment}
                </TableCell>
                <TableCell className="hidden sm:table-cell tabular-nums text-muted-foreground">
                  {c.tenureMonths} mois
                </TableCell>
                <TableCell className="hidden lg:table-cell text-muted-foreground">
                  {c.contract}
                </TableCell>
                <TableCell>
                  <RiskBadge score={c.riskScore} />
                </TableCell>
                <TableCell>
                  <ChevronRight className="size-4 text-muted-foreground" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  )
}
