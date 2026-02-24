import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'

export default function OfferStatsCard({ title, numerator, denominator, color = 'blue' }) {
  const percentage = denominator > 0 ? Math.round((numerator / denominator) * 100) : 0
  
  const colorClasses = {
    blue: 'text-blue-600',
    green: 'text-green-600',
    red: 'text-red-600',
    yellow: 'text-yellow-600'
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex items-baseline gap-2">
            <span className={`text-3xl font-bold ${colorClasses[color]}`}>
              {numerator}
            </span>
            <span className="text-muted-foreground">/ {denominator}</span>
          </div>
          <Progress value={percentage} className="h-2" />
          <div className="text-sm text-muted-foreground">
            {percentage}% completion
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
