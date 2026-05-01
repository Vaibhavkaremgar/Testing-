import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function UsageCard({ title, total, used, remaining, unlimited = false }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Total</p>
            <p className="mt-1 break-words text-xl font-semibold leading-tight">{unlimited ? 'Unlimited' : total}</p>
          </div>
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Used</p>
            <p className="mt-1 break-words text-xl font-semibold leading-tight text-amber-600">{used}</p>
          </div>
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Remaining</p>
            <p className="mt-1 break-words text-xl font-semibold leading-tight text-blue-600">{unlimited ? 'Unlimited' : remaining}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
