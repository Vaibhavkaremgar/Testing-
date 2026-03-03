import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api } from '@/lib/api'
import {
  ResponsiveContainer,
  CartesianGrid,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  FunnelChart,
  Funnel,
  LabelList
} from 'recharts'

const COLORS = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

const METRIC_META = {
  recruitment_funnel: { title: 'Recruitment Funnel', chartTypes: ['funnel'] },
  time_to_hire: { title: 'Time to Hire', chartTypes: ['area', 'line', 'bar'] },
  time_to_interview: { title: 'Time to Interview', chartTypes: ['line', 'bar', 'area'] },
  offer_acceptance_rate: { title: 'Offer Acceptance Rate', chartTypes: ['line', 'bar', 'pie'] },
  interview_to_hire_ratio: { title: 'Interview to Hire Ratio', chartTypes: ['line', 'bar'] },
  drop_off_rate: { title: 'Drop-off Rate', chartTypes: ['line', 'bar', 'area'] },
  total_hires: { title: 'Total Hires', chartTypes: ['bar', 'line', 'area'] },
  applications_per_job: { title: 'Applications per Job', chartTypes: ['bar', 'line'] },
  resume_score_distribution: { title: 'Resume Score Distribution', chartTypes: ['bar', 'pie', 'line'] },
  ai_interview_average_score: { title: 'AI Interview Average Score', chartTypes: ['line', 'bar', 'area'] },
  application_volume_trend: { title: 'Application Volume Trend', chartTypes: ['line', 'bar', 'area'] },
  source_of_candidates: { title: 'Source of Candidates', chartTypes: ['bar', 'pie', 'line'] },
  hires_per_recruiter: { title: 'Hires per Recruiter', chartTypes: ['bar', 'line', 'pie'] },
  avg_resume_review_time: { title: 'Avg Resume Review Time', chartTypes: ['line', 'bar', 'area'] },
  interview_scheduling_delay: { title: 'Interview Scheduling Delay', chartTypes: ['line', 'bar', 'area'] },
  recruiter_performance_score: { title: 'Recruiter Performance Score', chartTypes: ['bar', 'line', 'pie'] },
  top_skills: { title: 'Top Skills', chartTypes: ['bar', 'pie', 'line'] },
  skill_gap_analysis: { title: 'Skill Gap Analysis', chartTypes: ['bar', 'line', 'area'] },
  skill_demand_vs_supply: { title: 'Skill Demand vs Supply', chartTypes: ['bar', 'line', 'area'] },
  skill_vs_hire_success_rate: { title: 'Skill vs Hire Success Rate', chartTypes: ['bar', 'line', 'pie'] }
}

const GROUPING_OPTIONS = [
  { value: 'month', label: 'By Month' },
  { value: 'department', label: 'By Department' },
  { value: 'recruiter', label: 'By Recruiter' },
  { value: 'client', label: 'By Client' }
]

function getMetricDataKeys(type) {
  if (type === 'recruitment_funnel') return { xKey: 'stage', yKey: 'count' }
  if (type === 'resume_score_distribution') return { xKey: 'range', yKey: 'count' }
  if (type === 'top_skills' || type === 'skill_gap_analysis' || type === 'skill_demand_vs_supply' || type === 'skill_vs_hire_success_rate') {
    return { xKey: 'skill', yKey: 'count' }
  }
  if (type === 'source_of_candidates') return { xKey: 'department', yKey: 'hired' }
  return { xKey: 'month', yKey: 'value' }
}

function normalizeSeries(type, rows) {
  if (!Array.isArray(rows)) return []

  if (type === 'recruitment_funnel') {
    return rows.map((r, index) => ({
      id: `${r.stage || 'stage'}-${index}`,
      stage: r.stage || `Stage ${index + 1}`,
      count: Number(r.count || 0),
      conversion_percentage: Number(r.conversion_percentage || 0),
      dropoff_percentage: Number(r.dropoff_percentage || 0),
      avg_time_days: Number(r.avg_time_days || 0)
    }))
  }

  if (type === 'time_to_hire') {
    return rows.map((r, index) => ({
      id: `${r.month || 'item'}-${index}`,
      month: r.month || `Period ${index + 1}`,
      value: Number(r.avg_days || 0)
    }))
  }

  if (type === 'resume_score_distribution') {
    return rows.map((r, index) => ({
      id: `${r.range || 'item'}-${index}`,
      range: r.range || `Range ${index + 1}`,
      count: Number(r.count || 0)
    }))
  }

  if (type === 'top_skills' || type === 'skill_gap_analysis' || type === 'skill_demand_vs_supply' || type === 'skill_vs_hire_success_rate') {
    return rows.map((r, index) => ({
      id: `${r.skill || 'skill'}-${index}`,
      skill: r.skill || `Skill ${index + 1}`,
      count: Number(r.count || 0),
      avg_score: Number(r.avg_score || 0)
    }))
  }

  if (type === 'source_of_candidates') {
    return rows.map((r, index) => ({
      id: `${r.department || 'dept'}-${index}`,
      department: r.department || `Department ${index + 1}`,
      hired: Number(r.hired || 0),
      open: Number(r.open || 0)
    }))
  }

  return rows.map((r, index) => ({
    id: `${r.month || 'item'}-${index}`,
    month: r.month || `Period ${index + 1}`,
    value: Number(r.value || r.count || r.avg_score || 0)
  }))
}

function applyGrouping(rows, grouping, type) {
  if (!Array.isArray(rows)) return []
  if (rows.length === 0) return []

  const { yKey } = getMetricDataKeys(type)
  const grouped = new Map()

  rows.forEach((row, idx) => {
    let groupValue = row.month || row.range || row.skill || row.department || `Group ${idx + 1}`
    if (grouping === 'department') groupValue = row.department || row.skill || `Department ${idx + 1}`
    if (grouping === 'recruiter') groupValue = row.recruiter || row.assigned_to || `Recruiter ${idx + 1}`
    if (grouping === 'client') groupValue = row.client || row.company_name || `Client ${idx + 1}`

    const current = grouped.get(groupValue) || 0
    grouped.set(groupValue, current + Number(row[yKey] || row.value || row.count || 0))
  })

  const labelKey = grouping === 'month' ? 'month' : grouping
  return Array.from(grouped.entries()).map(([label, total]) => ({
    [labelKey]: label,
    value: total
  }))
}

export default function AnalyticsWidget({
  type,
  filters,
  chartType: initialChartType,
  grouping: initialGrouping = 'month'
}) {
  const metric = METRIC_META[type] || { title: type, chartTypes: ['bar', 'line', 'area', 'pie'] }
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [chartType, setChartType] = useState(initialChartType || metric.chartTypes[0] || 'bar')
  const [grouping, setGrouping] = useState(initialGrouping)

  useEffect(() => {
    let isMounted = true

    const fetchData = async () => {
      setLoading(true)
      setError('')
      try {
        const requestFilters = {
          date_range: filters?.dateRange,
          start_date: filters?.customStartDate,
          end_date: filters?.customEndDate,
          recruiter: filters?.recruiter,
          client: filters?.client,
          department: filters?.department,
          grouping
        }

        let raw = []
        if (type === 'recruitment_funnel') raw = await api.getRecruitmentFunnel(requestFilters)
        else if (type === 'time_to_hire') raw = await api.getTimeToHire(requestFilters)
        else if (type === 'resume_score_distribution') raw = await api.getScoreDistribution(requestFilters)
        else if (type === 'top_skills' || type === 'skill_gap_analysis' || type === 'skill_demand_vs_supply' || type === 'skill_vs_hire_success_rate') raw = await api.getSkillHeatmap(requestFilters)
        else if (type === 'source_of_candidates') raw = await api.getHiringByDepartment(requestFilters)
        else raw = await api.getTimeToHire(requestFilters)

        if (!isMounted) return
        setData(normalizeSeries(type, raw))
      } catch (err) {
        if (!isMounted) return
        setError(err?.message || 'Failed to load widget')
        setData([])
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    fetchData()
    return () => { isMounted = false }
  }, [type, filters, grouping])

  const groupedData = useMemo(() => applyGrouping(data, grouping, type), [data, grouping, type])
  const chartData = useMemo(() => {
    if (grouping === 'month') return data
    return groupedData
  }, [data, groupedData, grouping])

  const dataKeys = useMemo(() => {
    if (grouping === 'month') return getMetricDataKeys(type)
    return { xKey: grouping, yKey: 'value' }
  }, [grouping, type])

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <CardTitle className="text-base">{metric.title}</CardTitle>
          <div className="flex gap-2">
            <Select value={chartType} onValueChange={setChartType}>
              <SelectTrigger className="h-8 w-[110px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {metric.chartTypes.map((option) => (
                  <SelectItem key={option} value={option}>{option.toUpperCase()}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {type !== 'recruitment_funnel' && (
              <Select value={grouping} onValueChange={setGrouping}>
                <SelectTrigger className="h-8 w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {GROUPING_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex h-[260px] items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
          </div>
        ) : error ? (
          <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">{error}</div>
        ) : chartData.length === 0 ? (
          <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">No data available</div>
        ) : (
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              {chartType === 'bar' && (
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey={dataKeys.xKey} className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey={dataKeys.yKey} radius={[4, 4, 0, 0]}>
                    {chartData.map((_, index) => (
                      <Cell key={`bar-cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              )}
              {chartType === 'line' && (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey={dataKeys.xKey} className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Line type="monotone" dataKey={dataKeys.yKey} stroke="#3b82f6" strokeWidth={2} />
                </LineChart>
              )}
              {chartType === 'area' && (
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id={`widget-gradient-${type}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey={dataKeys.xKey} className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Area type="monotone" dataKey={dataKeys.yKey} stroke="#3b82f6" fill={`url(#widget-gradient-${type})`} />
                </AreaChart>
              )}
              {chartType === 'pie' && (
                <PieChart>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Pie data={chartData} dataKey={dataKeys.yKey} nameKey={dataKeys.xKey} cx="50%" cy="50%" outerRadius={90}>
                    {chartData.map((_, index) => (
                      <Cell key={`pie-cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                </PieChart>
              )}
              {chartType === 'funnel' && (
                <FunnelChart>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                    formatter={(value, name, payload) => {
                      if (name === 'count') return [`${value}`, 'Candidates']
                      return [value, name]
                    }}
                  />
                  <Funnel dataKey="count" data={chartData} isAnimationActive>
                    {chartData.map((_, index) => (
                      <Cell key={`funnel-cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                    <LabelList position="right" fill="#888" stroke="none" dataKey="stage" />
                    <LabelList position="center" fill="#fff" stroke="none" dataKey="count" />
                  </Funnel>
                </FunnelChart>
              )}
            </ResponsiveContainer>
          </div>
        )}
        {type === 'recruitment_funnel' && chartData.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="px-2 py-2 text-left font-medium">Stage</th>
                  <th className="px-2 py-2 text-left font-medium">Count</th>
                  <th className="px-2 py-2 text-left font-medium">Conversion %</th>
                  <th className="px-2 py-2 text-left font-medium">Drop-off %</th>
                  <th className="px-2 py-2 text-left font-medium">Avg Time (Days)</th>
                </tr>
              </thead>
              <tbody>
                {chartData.map((row) => (
                  <tr key={row.id} className="border-b">
                    <td className="px-2 py-2">{row.stage}</td>
                    <td className="px-2 py-2">{row.count}</td>
                    <td className="px-2 py-2">{row.conversion_percentage}%</td>
                    <td className="px-2 py-2">{row.dropoff_percentage}%</td>
                    <td className="px-2 py-2">{row.avg_time_days}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
