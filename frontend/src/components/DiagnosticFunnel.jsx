import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, TrendingDown, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function DiagnosticFunnel({ data }) {
  const [selectedDropoff, setSelectedDropoff] = useState(null)

  if (!data || !data.stages) return null

  const maxCount = Math.max(...data.stages.map(s => s.count))

  return (
    <div className="space-y-4">
      {/* Funnel Visualization */}
      <div className="space-y-3">
        {data.stages.map((stage, idx) => {
          const width = (stage.count / maxCount) * 100
          const dropoff = data.dropoffs.find(d => d.from_stage === stage.stage)
          
          return (
            <div key={stage.stage}>
              {/* Stage Bar */}
              <div className="relative">
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-sm font-medium w-24">{stage.stage}</span>
                  <div className="flex-1 bg-muted rounded-lg h-12 relative overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-lg transition-all flex items-center justify-between px-4",
                        idx === 0 ? "bg-blue-500" :
                        idx === 1 ? "bg-purple-500" :
                        idx === 2 ? "bg-orange-500" :
                        "bg-green-500"
                      )}
                      style={{ width: `${width}%` }}
                    >
                      <span className="text-white font-bold">{stage.count}</span>
                      <span className="text-white text-sm">{stage.percentage}%</span>
                    </div>
                  </div>
                </div>

                {/* Drop-off Indicator */}
                {dropoff && (
                  <div className="ml-28 mt-2 flex items-center gap-2">
                    <div className="flex-1 border-l-2 border-dashed border-muted-foreground/30 pl-4 py-2">
                      <div className="flex items-center gap-2">
                        <TrendingDown className={cn(
                          "h-4 w-4",
                          dropoff.is_abnormal ? "text-red-500" : "text-yellow-500"
                        )} />
                        <span className="text-sm text-muted-foreground">
                          {dropoff.dropped_count} dropped ({dropoff.dropoff_rate}%)
                        </span>
                        {dropoff.is_abnormal && (
                          <Badge variant="destructive" className="text-xs">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            Abnormal
                          </Badge>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2"
                          onClick={() => setSelectedDropoff(dropoff)}
                        >
                          <Info className="h-3 w-3 mr-1" />
                          Why?
                        </Button>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        Conversion: {dropoff.conversion_rate}%
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 pt-4 border-t">
        <div className="text-center">
          <p className="text-2xl font-bold">{data.total_candidates}</p>
          <p className="text-xs text-muted-foreground">Total Candidates</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-red-500">{data.rejected_total}</p>
          <p className="text-xs text-muted-foreground">Rejected ({data.rejection_rate}%)</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-green-500">
            {data.stages[data.stages.length - 1]?.count || 0}
          </p>
          <p className="text-xs text-muted-foreground">Selected</p>
        </div>
      </div>

      {/* Side Panel for Drop-off Details */}
      {selectedDropoff && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedDropoff(null)}>
          <div className="bg-card rounded-lg p-6 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Drop-off Analysis</h3>
              <Button variant="ghost" size="icon" onClick={() => setSelectedDropoff(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-sm text-muted-foreground">Stage Transition</p>
                <p className="text-lg font-semibold">
                  {selectedDropoff.from_stage} → {selectedDropoff.to_stage}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-muted p-3 rounded-lg">
                  <p className="text-xs text-muted-foreground">Dropped</p>
                  <p className="text-2xl font-bold text-red-500">{selectedDropoff.dropped_count}</p>
                </div>
                <div className="bg-muted p-3 rounded-lg">
                  <p className="text-xs text-muted-foreground">Drop-off Rate</p>
                  <p className="text-2xl font-bold">{selectedDropoff.dropoff_rate}%</p>
                </div>
              </div>

              <div className="bg-muted p-3 rounded-lg">
                <p className="text-xs text-muted-foreground mb-1">Conversion Rate</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-background rounded-full h-2">
                    <div
                      className="bg-green-500 h-2 rounded-full"
                      style={{ width: `${selectedDropoff.conversion_rate}%` }}
                    />
                  </div>
                  <span className="text-sm font-semibold">{selectedDropoff.conversion_rate}%</span>
                </div>
              </div>

              {selectedDropoff.is_abnormal && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-3 rounded-lg">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-red-900 dark:text-red-100">
                        Abnormal Drop-off Detected
                      </p>
                      <p className="text-xs text-red-800 dark:text-red-200 mt-1">
                        This drop-off rate exceeds 60%, indicating a potential issue in your hiring process.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 p-4 rounded-lg">
                <p className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
                  💡 AI Insight
                </p>
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  {selectedDropoff.reason}
                </p>
              </div>

              <div className="pt-2">
                <p className="text-xs text-muted-foreground mb-2">Recommendations:</p>
                <ul className="text-xs space-y-1 text-muted-foreground">
                  {selectedDropoff.dropoff_rate > 60 && (
                    <>
                      <li>• Review screening criteria - may be too strict</li>
                      <li>• Check response times - delays lose candidates</li>
                      <li>• Analyze competitor offers in market</li>
                    </>
                  )}
                  {selectedDropoff.dropoff_rate > 40 && selectedDropoff.dropoff_rate <= 60 && (
                    <>
                      <li>• Optimize job descriptions for clarity</li>
                      <li>• Improve candidate communication</li>
                      <li>• Consider salary competitiveness</li>
                    </>
                  )}
                  {selectedDropoff.dropoff_rate <= 40 && (
                    <>
                      <li>• Drop-off rate is healthy</li>
                      <li>• Continue current process</li>
                      <li>• Monitor for changes over time</li>
                    </>
                  )}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
