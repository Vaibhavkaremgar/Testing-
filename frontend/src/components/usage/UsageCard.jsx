import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function UsageCard({ title, total, used, remaining }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Total</p>
            <p className="mt-1 text-2xl font-semibold">{total}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Used</p>
            <p className="mt-1 text-2xl font-semibold text-amber-600">{used}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Remaining</p>
            <p className="mt-1 text-2xl font-semibold text-blue-600">{remaining}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
