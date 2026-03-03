import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'
import { Settings2, X } from 'lucide-react'
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

export default function Analytics() {
  const { user } = useAuth()

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

  const [isCustomizeOpen, setIsCustomizeOpen] = useState(false)
  const [selectedMetrics, setSelectedMetrics] = useState(DEFAULT_SELECTED_METRICS)
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

  const openCustomizeDrawer = () => {
    setDraftSelectedMetrics(selectedMetrics)
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
    setSelectedMetrics(draftSelectedMetrics)
    setIsCustomizeOpen(false)
  }

  if (loadingFilters) {
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

            <div className="ml-auto">
              <Button variant="outline" className="gap-2" onClick={openCustomizeDrawer}>
                <Settings2 className="h-4 w-4" />
                Customize Dashboard
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {selectedMetrics.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            No metrics selected. Click "Customize Dashboard" to choose metrics.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {selectedMetrics.map((metricId) => (
            <AnalyticsWidget
              key={metricId}
              type={metricId}
              filters={analyticsFilters}
            />
          ))}
        </div>
      )}

      {isCustomizeOpen && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={closeCustomizeDrawer} />
          <div className="absolute right-0 top-0 h-full w-full max-w-xl overflow-y-auto border-l bg-background shadow-xl">
            <div className="sticky top-0 z-10 border-b bg-background p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Customize Dashboard</h2>
                  <p className="text-sm text-muted-foreground">Choose metrics to display on Analytics</p>
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
