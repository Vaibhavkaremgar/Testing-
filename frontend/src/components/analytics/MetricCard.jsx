import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function MetricCard({ title, value, unit, change, isGood, icon: Icon }) {
  const isPositive = change > 0
  const showGreen = (isGood && isPositive) || (!isGood && !isPositive)
  
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {value}{unit}
        </div>
        {change !== undefined && (
          <div className={cn(
            "flex items-center text-xs mt-1",
            showGreen ? "text-green-600" : "text-red-600"
          )}>
            {isPositive ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
            {Math.abs(change)}% vs last week
          </div>
        )}
      </CardContent>
    </Card>
  )
}
