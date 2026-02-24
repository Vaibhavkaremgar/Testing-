import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Lightbulb, AlertCircle } from 'lucide-react'

export default function HiringIntelligence({ insights }) {
  if (!insights || insights.length === 0) {
    return null
  }

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Lightbulb className="h-5 w-5 text-blue-500" />
          Today's Hiring Intelligence
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {insights.map((insight, idx) => (
            <div key={idx} className="flex items-start gap-3 p-3 bg-muted/50 rounded-lg">
              <AlertCircle className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm leading-relaxed">{insight}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
