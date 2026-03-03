import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'
import { Settings2, X, TrendingUp, TrendingDown, Minus, GripVertical, Save, Lightbulb } from 'lucide-react'
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import AnalyticsWidget from '@/components/analytics/AnalyticsWidget'

const METRIC_CATEGORIES = [
  {
    title: 'Hiring Metrics',
    metrics: [
      { id: 'recruitment_funnel', label: 'Recruitment Funnel' },
      { id: 'time_to_hire', label: 'Time to Hire' },
      { id: 'time_to_interview', label: 'Time to Interview' },
      { id: 'offer_acceptance_rate', label: 'Offer Acceptance Rate' },
      { id: 'interview_to_hire_ratio', label: 'Interview to Hire Ratio' },
      { id: 'drop_off_rate', label: 'Drop-off Rate' },
      { id: 'total_hires', label: 'Total Hires' },
      { id: 'applications_per_job', label: 'Applications per Job' }
    ]
  },
  {
    title: 'Candidate Metrics',
    metrics: [
      { id: 'resume_score_distribution', label: 'Resume Score Distribution' },
      { id: 'ai_interview_average_score', label: 'AI Interview Average Score' },
      { id: 'application_volume_trend', label: 'Application Volume Trend' },
      { id: 'source_of_candidates', label: 'Source of Candidates' }
    ]
  },
  {
    title: 'Recruiter Metrics',
    metrics: [
      { id: 'hires_per_recruiter', label: 'Hires per Recruiter' },
      { id: 'avg_resume_review_time', label: 'Avg Resume Review Time' },
      { id: 'interview_scheduling_delay', label: 'Interview Scheduling Delay' },
      { id: 'recruiter_performance_score', label: 'Recruiter Performance Score' }
    ]
  },
  {
    title: 'Skill Metrics',
    metrics: [
      { id: 'top_skills', label: 'Top Skills' },
      { id: 'skill_gap_analysis', label: 'Skill Gap Analysis' },
      { id: 'skill_demand_vs_supply', label: 'Skill Demand vs Supply' },
      { id: 'skill_vs_hire_success_rate', label: 'Skill vs Hire Success Rate' }
    ]
  }
]

const DEFAULT_SELECTED_METRICS = [
  'recruitment_funnel',
  'time_to_hire',
  'resume_score_distribution',
  'top_skills',
  'skill_gap_analysis'
]

const SIZE_CLASS = {
  small: 'md:col-span-4',
  medium: 'md:col-span-6',
  large: 'md:col-span-12'
}

function toYmd(date) {
  const y = date.getUTCFullYear()
  const m = `${date.getUTCMonth() + 1}`.padStart(2, '0')
  const d = `${date.getUTCDate()}`.padStart(2, '0')
  return `${y}-${m}-${d}`
}

function resolveCurrentAndPreviousRanges(dateRange, customStartDate, customEndDate) {
  const now = new Date()
  let currentStart
  let currentEnd

  if (dateRange === 'last_7_days') {
    currentStart = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    currentEnd = now
  } else if (dateRange === 'last_3_months') {
    currentStart = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
    currentEnd = now
  } else if (dateRange === 'last_6_months') {
    currentStart = new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000)
    currentEnd = now
  } else if (dateRange === 'custom' && customStartDate && customEndDate) {
    currentStart = new Date(`${customStartDate}T00:00:00Z`)
    currentEnd = new Date(`${customEndDate}T23:59:59Z`)
  } else {
    currentStart = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
    currentEnd = now
  }

  const duration = currentEnd.getTime() - currentStart.getTime()
  const previousEnd = new Date(currentStart.getTime())
  const previousStart = new Date(previousEnd.getTime() - duration)

  return {
    currentStart: toYmd(currentStart),
    currentEnd: toYmd(currentEnd),
    previousStart: toYmd(previousStart),
    previousEnd: toYmd(previousEnd),
  }
}

function getInterviewStageDropoff(funnelRows) {
  if (!Array.isArray(funnelRows) || funnelRows.length === 0) return 0
  const interviewed = funnelRows.find((row) => String(row?.stage || '').toLowerCase() === 'interviewed')
  if (interviewed && Number.isFinite(Number(interviewed.dropoff_percentage))) {
    return Number(interviewed.dropoff_percentage)
  }
  const shortlisted = funnelRows.find((row) => String(row?.stage || '').toLowerCase() === 'shortlisted')
  if (shortlisted && Number.isFinite(Number(shortlisted.dropoff_percentage))) {
    return Number(shortlisted.dropoff_percentage)
  }
  return 0
}

function normalizePct(value) {
  return Number.isFinite(Number(value)) ? Math.abs(Number(value)).toFixed(1) : '0.0'
}

function buildDefaultLayout(allMetricIds) {
  return allMetricIds.map((metricKey, index) => ({
    metricKey,
    position: index,
    size: DEFAULT_SELECTED_METRICS.includes(metricKey) ? 'medium' : 'medium',
    isEnabled: DEFAULT_SELECTED_METRICS.includes(metricKey),
  }))
}

function SortableWidgetTile({ item, filters, onResize, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: item.metricKey })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn('col-span-12', SIZE_CLASS[item.size] || SIZE_CLASS.medium)}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-3.5 w-3.5" />
          Drag
        </button>
        <div className="flex items-center gap-2">
          <Select value={item.size} onValueChange={(value) => onResize(item.metricKey, value)}>
            <SelectTrigger className="h-7 w-[110px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="small">Small</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="large">Large</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="ghost" size="sm" onClick={() => onRemove(item.metricKey)}>
            Remove
          </Button>
        </div>
      </div>
      <AnalyticsWidget type={item.metricKey} filters={filters} />
    </div>
  )
}

export default function Analytics() {
  const { user } = useAuth()
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))

  const [dateRange, setDateRange] = useState('last_30_days')
  const [customStartDate, setCustomStartDate] = useState('')
  const [customEndDate, setCustomEndDate] = useState('')
  const [compareMode, setCompareMode] = useState(false)
  const [compareType, setCompareType] = useState('previous_period')
  const [selectedClient, setSelectedClient] = useState('all')
  const [selectedRecruiter, setSelectedRecruiter] = useState('all')
  const [selectedDepartment, setSelectedDepartment] = useState('all')

  const [clients, setClients] = useState([])
  const [recruiters, setRecruiters] = useState([])
  const [departments, setDepartments] = useState([])
  const [loadingFilters, setLoadingFilters] = useState(true)
  const [kpiSummary, setKpiSummary] = useState([])
  const [kpiLoading, setKpiLoading] = useState(false)
  const [smartInsights, setSmartInsights] = useState([])
  const [insightsLoading, setInsightsLoading] = useState(false)

  const allMetrics = useMemo(
    () => METRIC_CATEGORIES.flatMap((category) => category.metrics),
    []
  )
  const allMetricIds = useMemo(() => allMetrics.map((m) => m.id), [allMetrics])

  const [widgetLayout, setWidgetLayout] = useState(buildDefaultLayout(allMetricIds))
  const [layoutLoading, setLayoutLoading] = useState(true)
  const [layoutSaving, setLayoutSaving] = useState(false)
  const [isCustomizeOpen, setIsCustomizeOpen] = useState(false)
  const [draftSelectedMetrics, setDraftSelectedMetrics] = useState(DEFAULT_SELECTED_METRICS)

  const isAdmin = user?.role === 'admin'
  const canFilterRecruiters = user?.role === 'admin' || user?.role === 'hiring_manager'

  useEffect(() => {
    const fetchFilterOptions = async () => {
      setLoadingFilters(true)
      try {
        const [jobsData, usersData] = await Promise.all([
          api.getJobs({ limit: 1000 }).catch(() => []),
          api.getPublicUsers().catch(() => [])
        ])

        const uniqueClients = Array.from(
          new Set((jobsData || []).map((job) => job.company_name).filter(Boolean))
        ).sort((a, b) => a.localeCompare(b))

        const uniqueDepartments = Array.from(
          new Set((jobsData || []).map((job) => job.department).filter(Boolean))
        ).sort((a, b) => a.localeCompare(b))

        const recruiterUsers = (usersData || []).filter((u) => u?.role === 'recruiter')

        setClients(uniqueClients)
        setDepartments(uniqueDepartments)
        setRecruiters(recruiterUsers)

        if (user?.role === 'recruiter' && user?.id) {
          setSelectedRecruiter(String(user.id))
        }
      } catch (error) {
        console.error('Failed to fetch analytics filter options:', error)
      } finally {
        setLoadingFilters(false)
      }
    }

    fetchFilterOptions()
  }, [user?.id, user?.role])

  useEffect(() => {
    const fetchLayout = async () => {
      setLayoutLoading(true)
      try {
        await api.getAnalyticsWidgetCatalog().catch(() => [])
        const response = await api.getAnalyticsWidgetLayout()
        const items = Array.isArray(response?.items) ? response.items : []
        if (items.length === 0) {
          setWidgetLayout(buildDefaultLayout(allMetricIds))
        } else {
          const normalized = items
            .filter((item) => allMetricIds.includes(item.metric_key))
            .map((item, index) => ({
              metricKey: item.metric_key,
              position: Number.isFinite(item.position) ? item.position : index,
              size: ['small', 'medium', 'large'].includes(item.size) ? item.size : 'medium',
              isEnabled: item.is_enabled !== false,
            }))

          const existingKeys = new Set(normalized.map((item) => item.metricKey))
          const missing = allMetricIds
            .filter((metricKey) => !existingKeys.has(metricKey))
            .map((metricKey, index) => ({
              metricKey,
              position: normalized.length + index,
              size: 'medium',
              isEnabled: false,
            }))

          setWidgetLayout([...normalized, ...missing])
        }
      } catch (error) {
        console.error('Failed to fetch widget layout:', error)
        setWidgetLayout(buildDefaultLayout(allMetricIds))
      } finally {
        setLayoutLoading(false)
      }
    }

    fetchLayout()
  }, [allMetricIds])

  const visibleWidgets = useMemo(() => {
    return widgetLayout
      .filter((item) => item.isEnabled && allMetricIds.includes(item.metricKey))
      .sort((a, b) => a.position - b.position)
  }, [widgetLayout, allMetricIds])

  const analyticsFilters = useMemo(() => {
    return {
      dateRange,
      customStartDate: dateRange === 'custom' ? customStartDate : '',
      customEndDate: dateRange === 'custom' ? customEndDate : '',
      compareMode,
      compareType: compareMode ? compareType : '',
      recruiter: selectedRecruiter,
      client: selectedClient,
      department: selectedDepartment
    }
  }, [
    dateRange,
    customStartDate,
    customEndDate,
    compareMode,
    compareType,
    selectedRecruiter,
    selectedClient,
    selectedDepartment
  ])

  useEffect(() => {
    const fetchKpiSummary = async () => {
      setKpiLoading(true)
      try {
        const response = await api.getKpiSummary({
          date_range: analyticsFilters.dateRange,
          start_date: analyticsFilters.customStartDate,
          end_date: analyticsFilters.customEndDate,
          recruiter: analyticsFilters.recruiter,
          client: analyticsFilters.client,
          department: analyticsFilters.department
        })
        setKpiSummary(response?.kpis || [])
      } catch (error) {
        console.error('Failed to fetch KPI summary:', error)
        setKpiSummary([])
      } finally {
        setKpiLoading(false)
      }
    }

    fetchKpiSummary()
  }, [analyticsFilters])

  useEffect(() => {
    const fetchSmartInsights = async () => {
      setInsightsLoading(true)
      try {
        const ranges = resolveCurrentAndPreviousRanges(
          analyticsFilters.dateRange,
          analyticsFilters.customStartDate,
          analyticsFilters.customEndDate
        )

        const currentParams = {
          date_range: 'custom',
          start_date: ranges.currentStart,
          end_date: ranges.currentEnd,
          recruiter: analyticsFilters.recruiter,
          client: analyticsFilters.client,
          department: analyticsFilters.department
        }

        const previousParams = {
          date_range: 'custom',
          start_date: ranges.previousStart,
          end_date: ranges.previousEnd,
          recruiter: analyticsFilters.recruiter,
          client: analyticsFilters.client,
          department: analyticsFilters.department
        }

        const [currentFunnel, previousFunnel] = await Promise.all([
          api.getRecruitmentFunnel(currentParams).catch(() => []),
          api.getRecruitmentFunnel(previousParams).catch(() => [])
        ])

        const currentInterviewDropoff = getInterviewStageDropoff(currentFunnel)
        const previousInterviewDropoff = getInterviewStageDropoff(previousFunnel)
        const interviewDropoffDelta = Number((currentInterviewDropoff - previousInterviewDropoff).toFixed(1))

        let departmentInsight = null
        const departmentsToCompare =
          analyticsFilters.department && analyticsFilters.department !== 'all'
            ? [analyticsFilters.department]
            : departments.slice(0, 12)

        if (departmentsToCompare.length > 0) {
          const departmentFunnels = await Promise.all(
            departmentsToCompare.map(async (dept) => {
              const rows = await api.getRecruitmentFunnel({
                ...currentParams,
                department: dept
              }).catch(() => [])
              return { dept, dropoff: getInterviewStageDropoff(rows) }
            })
          )

          const highest = departmentFunnels.sort((a, b) => b.dropoff - a.dropoff)[0]
          if (highest && Number.isFinite(highest.dropoff)) {
            departmentInsight = highest
          }
        }

        const kpiByKey = new Map((kpiSummary || []).map((kpi) => [kpi.key, kpi]))
        const hiresKpi = kpiByKey.get('total_hires')
        const offerAcceptanceKpi = kpiByKey.get('offer_acceptance_rate')

        const generated = []

        if (hiresKpi) {
          generated.push(
            hiresKpi.change_pct >= 0
              ? `Hiring increased by ${normalizePct(hiresKpi.change_pct)}% this period`
              : `Hiring decreased by ${normalizePct(hiresKpi.change_pct)}% this period`
          )
        }

        if (departmentInsight) {
          generated.push(
            `${departmentInsight.dept} has the highest interview-stage drop-off rate at ${normalizePct(departmentInsight.dropoff)}%`
          )
        }

        generated.push(
          interviewDropoffDelta >= 0
            ? `AI interview rejection rate increased by ${normalizePct(interviewDropoffDelta)}% vs previous period`
            : `AI interview rejection rate decreased by ${normalizePct(interviewDropoffDelta)}% vs previous period`
        )

        if (offerAcceptanceKpi) {
          generated.push(
            offerAcceptanceKpi.change_pct >= 0
              ? `Offer acceptance improved by ${normalizePct(offerAcceptanceKpi.change_pct)}%`
              : `Offer acceptance dropped by ${normalizePct(offerAcceptanceKpi.change_pct)}%`
          )
        }

        setSmartInsights(generated.slice(0, 4))
      } catch (error) {
        console.error('Failed to generate smart insights:', error)
        setSmartInsights([])
      } finally {
        setInsightsLoading(false)
      }
    }

    if (kpiSummary.length > 0 || departments.length > 0) {
      fetchSmartInsights()
    } else {
      setSmartInsights([])
    }
  }, [analyticsFilters, departments, kpiSummary])

  const formatKpiValue = (kpi) => {
    if (kpi.key === 'offer_acceptance_rate') return `${kpi.value}%`
    if (kpi.key === 'interview_to_hire_ratio') return `${kpi.value}x`
    if (kpi.key === 'avg_time_to_hire') return `${kpi.value}d`
    return `${kpi.value}`
  }

  const getTrendIcon = (trend) => {
    if (trend === 'up') return TrendingUp
    if (trend === 'down') return TrendingDown
    return Minus
  }

  const getTrendClass = (trend) => {
    if (trend === 'up') return 'text-emerald-600'
    if (trend === 'down') return 'text-rose-600'
    return 'text-muted-foreground'
  }

  const openCustomizeDrawer = () => {
    setDraftSelectedMetrics(visibleWidgets.map((item) => item.metricKey))
    setIsCustomizeOpen(true)
  }

  const closeCustomizeDrawer = () => {
    setIsCustomizeOpen(false)
  }

  const toggleMetricInDraft = (metricId) => {
    setDraftSelectedMetrics((prev) => {
      if (prev.includes(metricId)) return prev.filter((id) => id !== metricId)
      return [...prev, metricId]
    })
  }

  const applyDashboardCustomization = () => {
    const currentVisibleOrder = visibleWidgets.map((item) => item.metricKey)
    const nextOrder = [
      ...currentVisibleOrder.filter((metricKey) => draftSelectedMetrics.includes(metricKey)),
      ...draftSelectedMetrics.filter((metricKey) => !currentVisibleOrder.includes(metricKey))
    ]

    setWidgetLayout((prev) => {
      const prevMap = new Map(prev.map((item) => [item.metricKey, item]))
      return allMetricIds.map((metricKey) => {
        const existing = prevMap.get(metricKey)
        const isEnabled = nextOrder.includes(metricKey)
        return {
          metricKey,
          size: existing?.size || 'medium',
          isEnabled,
          position: isEnabled ? nextOrder.indexOf(metricKey) : (existing?.position ?? 999),
        }
      })
    })
    setIsCustomizeOpen(false)
  }

  const handleResizeWidget = (metricKey, size) => {
    setWidgetLayout((prev) => prev.map((item) => (
      item.metricKey === metricKey ? { ...item, size } : item
    )))
  }

  const handleRemoveWidget = (metricKey) => {
    setWidgetLayout((prev) => {
      const next = prev.map((item) => (
        item.metricKey === metricKey ? { ...item, isEnabled: false } : item
      ))
      const visible = next.filter((item) => item.isEnabled).sort((a, b) => a.position - b.position)
      return next.map((item) => {
        if (!item.isEnabled) return item
        return { ...item, position: visible.findIndex((v) => v.metricKey === item.metricKey) }
      })
    })
  }

  const handleDragEnd = (event) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = visibleWidgets.findIndex((item) => item.metricKey === active.id)
    const newIndex = visibleWidgets.findIndex((item) => item.metricKey === over.id)
    if (oldIndex < 0 || newIndex < 0) return

    const reordered = arrayMove(visibleWidgets, oldIndex, newIndex)
    const positionMap = new Map(reordered.map((item, index) => [item.metricKey, index]))

    setWidgetLayout((prev) => prev.map((item) => (
      item.isEnabled && positionMap.has(item.metricKey)
        ? { ...item, position: positionMap.get(item.metricKey) }
        : item
    )))
  }

  const handleSaveLayout = async () => {
    setLayoutSaving(true)
    try {
      const payload = widgetLayout.map((item, index) => ({
        metric_key: item.metricKey,
        position: Number.isFinite(item.position) ? item.position : index,
        size: item.size || 'medium',
        is_enabled: item.isEnabled,
      }))
      await api.saveAnalyticsWidgetLayout(payload)
    } catch (error) {
      console.error('Failed to save dashboard layout:', error)
    } finally {
      setLayoutSaving(false)
    }
  }

  if (loadingFilters || layoutLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Analytics</h1>
        <p className="text-muted-foreground">Hiring metrics and insights</p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Lightbulb className="h-4 w-4 text-amber-500" />
            Smart Insight Panel
          </CardTitle>
        </CardHeader>
        <CardContent>
          {insightsLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="h-4 w-4 animate-spin rounded-full border-b-2 border-primary"></div>
              Generating insights from current analytics data...
            </div>
          ) : smartInsights.length === 0 ? (
            <p className="text-sm text-muted-foreground">No insights available for current filters.</p>
          ) : (
            <div className="grid gap-2">
              {smartInsights.map((insight, index) => (
                <div key={`${insight}-${index}`} className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
                  {insight}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[180px] space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Date Range</p>
              <Select value={dateRange} onValueChange={setDateRange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="last_7_days">Last 7 Days</SelectItem>
                  <SelectItem value="last_30_days">Last 30 Days</SelectItem>
                  <SelectItem value="last_3_months">Last 3 Months</SelectItem>
                  <SelectItem value="last_6_months">Last 6 Months</SelectItem>
                  <SelectItem value="custom">Custom Range</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {dateRange === 'custom' && (
              <>
                <div className="min-w-[160px] space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">Start Date</p>
                  <input
                    type="date"
                    value={customStartDate}
                    onChange={(e) => setCustomStartDate(e.target.value)}
                    className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
                <div className="min-w-[160px] space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">End Date</p>
                  <input
                    type="date"
                    value={customEndDate}
                    onChange={(e) => setCustomEndDate(e.target.value)}
                    className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
              </>
            )}

            <div className="min-w-[220px] space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Compare Mode</p>
              <div className="flex h-10 items-center gap-2 rounded-md border border-input px-3">
                <Switch checked={compareMode} onCheckedChange={setCompareMode} />
                <span className="text-sm">{compareMode ? 'Enabled' : 'Disabled'}</span>
              </div>
            </div>

            {compareMode && (
              <div className="min-w-[220px] space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Compare By</p>
                <Select value={compareType} onValueChange={setCompareType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="previous_period">Compare with Previous Period</SelectItem>
                    <SelectItem value="recruiter">Compare Recruiter</SelectItem>
                    <SelectItem value="department">Compare Department</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="min-w-[200px] space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Department</p>
              <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                <SelectTrigger>
                  <SelectValue placeholder="All Departments" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {departments.map((department) => (
                    <SelectItem key={department} value={department}>
                      {department}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {isAdmin && (
              <div className="min-w-[200px] space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Client</p>
                <Select value={selectedClient} onValueChange={setSelectedClient}>
                  <SelectTrigger>
                    <SelectValue placeholder="All Clients" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Clients</SelectItem>
                    {clients.map((clientName) => (
                      <SelectItem key={clientName} value={clientName}>
                        {clientName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {(canFilterRecruiters || user?.role === 'recruiter') && (
              <div className="min-w-[220px] space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Recruiter</p>
                {canFilterRecruiters ? (
                  <Select value={selectedRecruiter} onValueChange={setSelectedRecruiter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All Recruiters" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Recruiters</SelectItem>
                      {recruiters.map((recruiter) => (
                        <SelectItem key={recruiter.id} value={String(recruiter.id)}>
                          {recruiter.full_name || recruiter.email}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <div className="flex h-10 items-center rounded-md border border-input px-3 text-sm text-muted-foreground">
                    {user?.full_name || 'Assigned Recruiter'}
                  </div>
                )}
              </div>
            )}

            <div className="ml-auto flex items-center gap-2">
              <Button variant="outline" className="gap-2" onClick={handleSaveLayout} disabled={layoutSaving}>
                <Save className="h-4 w-4" />
                {layoutSaving ? 'Saving...' : 'Save Layout'}
              </Button>
              <Button variant="outline" className="gap-2" onClick={openCustomizeDrawer}>
                <Settings2 className="h-4 w-4" />
                Customize Dashboard
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div>
        <div className="mb-3">
          <h2 className="text-lg font-semibold">KPI Summary</h2>
          <p className="text-sm text-muted-foreground">Current values vs previous period</p>
        </div>
        {kpiLoading ? (
          <Card>
            <CardContent className="flex h-24 items-center justify-center p-4">
              <div className="h-6 w-6 animate-spin rounded-full border-b-2 border-primary"></div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {kpiSummary.map((kpi) => {
              const TrendIcon = getTrendIcon(kpi.trend)
              const trendClass = getTrendClass(kpi.trend)
              const changeLabel = `${kpi.change_pct > 0 ? '+' : ''}${kpi.change_pct}%`
              return (
                <Card key={kpi.key}>
                  <CardContent className="p-4">
                    <p className="text-sm text-muted-foreground">{kpi.label}</p>
                    <p className="mt-2 text-2xl font-bold">{formatKpiValue(kpi)}</p>
                    <div className={`mt-3 flex items-center gap-2 text-sm ${trendClass}`}>
                      <TrendIcon className="h-4 w-4" />
                      <span>{changeLabel} vs previous period</span>
                      <span className="ml-auto text-xs">{kpi.trend === 'flat' ? 'flat' : kpi.trend}</span>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </div>

      {visibleWidgets.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            No widgets selected. Click "Customize Dashboard" to add widgets.
          </CardContent>
        </Card>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={visibleWidgets.map((item) => item.metricKey)} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-12">
              {visibleWidgets.map((item) => (
                <SortableWidgetTile
                  key={item.metricKey}
                  item={item}
                  filters={analyticsFilters}
                  onResize={handleResizeWidget}
                  onRemove={handleRemoveWidget}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {isCustomizeOpen && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={closeCustomizeDrawer} />
          <div className="absolute right-0 top-0 h-full w-full max-w-xl overflow-y-auto border-l bg-background shadow-xl">
            <div className="sticky top-0 z-10 border-b bg-background p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Customize Dashboard</h2>
                  <p className="text-sm text-muted-foreground">Choose widgets to show or hide</p>
                </div>
                <Button variant="ghost" size="icon" onClick={closeCustomizeDrawer}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="space-y-6 p-5 pb-28">
              {METRIC_CATEGORIES.map((category) => (
                <Card key={category.title}>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">{category.title}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {category.metrics.map((metric) => (
                      <label key={metric.id} className="flex cursor-pointer items-center gap-3 text-sm">
                        <input
                          type="checkbox"
                          checked={draftSelectedMetrics.includes(metric.id)}
                          onChange={() => toggleMetricInDraft(metric.id)}
                          className="h-4 w-4 rounded border-input"
                        />
                        <span>{metric.label}</span>
                      </label>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="fixed bottom-0 right-0 w-full max-w-xl border-t bg-background p-5">
              <div className="flex items-center justify-end gap-2">
                <Button variant="outline" onClick={closeCustomizeDrawer}>Cancel</Button>
                <Button onClick={applyDashboardCustomization}>Apply</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
