import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api } from '@/lib/api'
import { AlertTriangle } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, FunnelChart, Funnel, LabelList
} from 'recharts'

const STAGE_COLORS = {
  screening: '#3b82f6',
  scheduling: '#8b5cf6',
  technical: '#ef4444',
  offer: '#10b981'
}

export default function TimeToHire() {
  const [data, setData] = useState([])
  const [department, setDepartment] = useState('all')
  const [role, setRole] = useState('all')
  const [loading, setLoading] = useState(true)
  const [departments] = useState(['all', 'Engineering', 'Sales', 'Marketing', 'HR'])
  const [roles] = useState(['all', 'Senior Engineer', 'Junior Developer', 'Sales Manager'])

  useEffect(() => {
    fetchData()
  }, [department, role])

  const fetchData = async () => {
    setLoading(true)
    try {
      const params = {}
      if (department !== 'all') params.department = department
      if (role !== 'all') params.role = role
      const result = await api.getTimeToHireStages(params)
      setData(result)
    } catch (error) {
      console.error('Failed to fetch time-to-hire data:', error)
    } finally {
      setLoading(false)
    }
  }

  const calculateAverages = () => {
    if (data.length === 0) return null
    const totals = { screening: 0, scheduling: 0, technical: 0, offer: 0 }
    data.forEach(d => {
      totals.screening += d.screening
      totals.scheduling += d.scheduling
      totals.technical += d.technical
      totals.offer += d.offer
    })
    return {
      screening: (totals.screening / data.length).toFixed(1),
      scheduling: (totals.scheduling / data.length).toFixed(1),
      technical: (totals.technical / data.length).toFixed(1),
      offer: (totals.offer / data.length).toFixed(1)
    }
  }

  const getSlowestStage = () => {
    const avgs = calculateAverages()
    if (!avgs) return null
    const stages = Object.entries(avgs).map(([name, value]) => ({ name, value: parseFloat(value) }))
    return stages.reduce((max, stage) => stage.value > max.value ? stage : max)
  }

  const getFunnelData = () => {
    if (data.length === 0) return []
    const latest = data[data.length - 1]
    const total = 100
    return [
      { stage: 'Resume Screening', count: total, dropoff: 0 },
      { stage: 'Interview Scheduling', count: total - (latest.dropoff * 0.3), dropoff: latest.dropoff * 0.3 },
      { stage: 'Technical Round', count: total - (latest.dropoff * 0.7), dropoff: latest.dropoff * 0.4 },
      { stage: 'Offer to Join', count: total - latest.dropoff, dropoff: latest.dropoff * 0.3 }
    ]
  }

  const avgs = calculateAverages()
  const slowest = getSlowestStage()
  const funnelData = getFunnelData()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Time to Hire Analysis</h1>
          <p className="text-muted-foreground">Stage-wise breakdown of hiring timeline</p>
        </div>
        <div className="flex gap-3">
          <Select value={department} onValueChange={setDepartment}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Department" />
            </SelectTrigger>
            <SelectContent>
              {departments.map(d => (
                <SelectItem key={d} value={d}>{d === 'all' ? 'All Departments' : d}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Role" />
            </SelectTrigger>
            <SelectContent>
              {roles.map(r => (
                <SelectItem key={r} value={r}>{r === 'all' ? 'All Roles' : r}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Stage Averages */}
      {avgs && (
        <div className="grid gap-4 md:grid-cols-4">
          {Object.entries(avgs).map(([stage, days]) => (
            <Card key={stage} className={slowest?.name === stage ? 'border-red-500 border-2' : ''}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground capitalize">{stage.replace('_', ' ')}</p>
                    <p className="text-3xl font-bold mt-1">{days} days</p>
                  </div>
                  {slowest?.name === stage && (
                    <AlertTriangle className="h-6 w-6 text-red-500" />
                  )}
                </div>
                {slowest?.name === stage && (
                  <p className="text-xs text-red-600 mt-2 font-medium">Bottleneck detected</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Stacked Bar Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Time Spent by Stage (Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="month" className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="screening" stackId="a" fill={STAGE_COLORS.screening} name="Resume Screening" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="scheduling" stackId="a" fill={STAGE_COLORS.scheduling} name="Interview Scheduling" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="technical" stackId="a" fill={STAGE_COLORS.technical} name="Technical Round" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="offer" stackId="a" fill={STAGE_COLORS.offer} name="Offer to Join" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Funnel Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Candidate Progression & Drop-off</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <FunnelChart>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Funnel dataKey="count" data={funnelData} isAnimationActive>
                    {funnelData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={Object.values(STAGE_COLORS)[index]} />
                    ))}
                    <LabelList position="right" fill="#888" stroke="none" dataKey="stage" />
                    <LabelList position="center" fill="#fff" stroke="none" dataKey="count" formatter={(value) => `${value.toFixed(0)}%`} />
                  </Funnel>
                </FunnelChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Stage Legend */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Stage Definitions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex items-start gap-3">
              <div className="w-4 h-4 rounded mt-1" style={{ backgroundColor: STAGE_COLORS.screening }}></div>
              <div>
                <p className="font-medium">Resume Screening</p>
                <p className="text-sm text-muted-foreground">Time from application to initial review completion</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-4 h-4 rounded mt-1" style={{ backgroundColor: STAGE_COLORS.scheduling }}></div>
              <div>
                <p className="font-medium">Interview Scheduling</p>
                <p className="text-sm text-muted-foreground">Time to coordinate and schedule interview slots</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-4 h-4 rounded mt-1" style={{ backgroundColor: STAGE_COLORS.technical }}></div>
              <div>
                <p className="font-medium">Technical Round</p>
                <p className="text-sm text-muted-foreground">Interview completion and evaluation period</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-4 h-4 rounded mt-1" style={{ backgroundColor: STAGE_COLORS.offer }}></div>
              <div>
                <p className="font-medium">Offer to Join</p>
                <p className="text-sm text-muted-foreground">Time from offer letter to candidate acceptance</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
