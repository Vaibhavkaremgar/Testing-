import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function ComparisonPanel({ technical, nonTechnical }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Technical vs Non-Technical Hiring</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold mb-3 text-blue-600">Technical Hiring</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Days to Hire:</span>
                <span className="font-medium">{technical.days_to_hire}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Days to Fill:</span>
                <span className="font-medium">{technical.days_to_fill}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Acceptance Rate:</span>
                <span className="font-medium">{technical.acceptance_rate}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Withdrawal Rate:</span>
                <span className="font-medium">{technical.withdrawal_rate}%</span>
              </div>
            </div>
          </div>
          <div>
            <h3 className="font-semibold mb-3 text-green-600">Non-Technical Hiring</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Days to Hire:</span>
                <span className="font-medium">{nonTechnical.days_to_hire}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Days to Fill:</span>
                <span className="font-medium">{nonTechnical.days_to_fill}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Acceptance Rate:</span>
                <span className="font-medium">{nonTechnical.acceptance_rate}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Withdrawal Rate:</span>
                <span className="font-medium">{nonTechnical.withdrawal_rate}%</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
