import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export default function PipelineTable({ data }) {
  const getBottleneck = (row) => {
    const conversion = row.first_interview / row.applicants
    if (conversion < 0.2) return 'low-conversion'
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Current Hiring Pipeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3 font-medium">Role</th>
                <th className="text-center p-3 font-medium">Leads</th>
                <th className="text-center p-3 font-medium">Applicants</th>
                <th className="text-center p-3 font-medium">1st Interview</th>
                <th className="text-center p-3 font-medium">2nd Interview</th>
                <th className="text-center p-3 font-medium">Final Interview</th>
                <th className="text-center p-3 font-medium">Offers</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, idx) => (
                <tr key={idx} className="border-b hover:bg-muted/50 cursor-pointer">
                  <td className="p-3">
                    <div>
                      <div className="font-medium">{row.role}</div>
                      <Badge variant="outline" className="text-xs mt-1">
                        {row.department}
                      </Badge>
                    </div>
                  </td>
                  <td className="text-center p-3">{row.leads}</td>
                  <td className="text-center p-3">{row.applicants}</td>
                  <td className="text-center p-3">
                    <span className={getBottleneck(row) ? 'text-red-600 font-semibold' : ''}>
                      {row.first_interview}
                    </span>
                  </td>
                  <td className="text-center p-3">{row.second_interview}</td>
                  <td className="text-center p-3">{row.final_interview}</td>
                  <td className="text-center p-3 font-semibold">{row.offers}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
