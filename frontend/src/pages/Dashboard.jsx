import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { cn, getScoreColor, formatDate } from '@/lib/utils'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import HiringIntelligence from '@/components/HiringIntelligence'
import {
  Users, UserCheck, UserX, Calendar, Award, FileText, X, CalendarIcon, Briefcase, Clock, CheckCircle, DollarSign, Target, TrendingDown
} from 'lucide-react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from 'recharts'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

const SAVED_DASHBOARD_VIEWS_KEY = 'dashboardSavedViews'
const LOW_CREDIT_MODAL_DISMISSED_KEY = 'dashboardLowCreditModalDismissed'
const INTERVIEW_REJECTION_SCORE_THRESHOLD = 6
const CANDIDATE_OWNED_STAGES = new Set(['REVIEW', 'SHORTLISTED', 'RESUME_REJECTED', 'INTERVIEW_RESCHEDULED', 'NO_SHOW'])
const INTERVIEW_OWNED_STAGES = new Set(['INTERVIEW_SCHEDULED', 'INTERVIEWED', 'SELECTED', 'REJECTED'])

function resolveDashboardDisplayStage(candidate, latestInterview) {
  if (candidate?.stage === 'INTERVIEW_RESCHEDULED' || candidate?.stage === 'NO_SHOW') {
    return candidate.stage
  }

  if (latestInterview) {
    const status = (latestInterview.status || '').trim().toLowerCase()
    if (status === 'completed') {
      const interviewScore = latestInterview.interview_score ?? 0
      return interviewScore >= INTERVIEW_REJECTION_SCORE_THRESHOLD ? 'SELECTED' : 'REJECTED'
    }

    if (status === 'ongoing') {
      return 'INTERVIEWED'
    }

    if (status === 'scheduled') {
      return 'INTERVIEW_SCHEDULED'
    }
  }

  const effectiveThreshold = candidate?.score_threshold || 60
  if (candidate?.resume_score !== undefined && candidate?.resume_score !== null && candidate.resume_score <= (effectiveThreshold - 10)) {
    return 'RESUME_REJECTED'
  }

  if (CANDIDATE_OWNED_STAGES.has(candidate?.stage)) {
    return candidate.stage
  }

  if (INTERVIEW_OWNED_STAGES.has(candidate?.stage)) {
    return 'SHORTLISTED'
  }

  return candidate?.stage
}

const getDefaultView = () => ({
  selectedMonth: 'all',
  selectedDate: null,
  selectedYear: new Date().getFullYear(),
  selectedMonthNum: null
})

function buildDashboardCandidateBuckets(candidatesData = [], interviewRows = []) {
  const candidateMap = new Map((candidatesData || []).map((candidate) => [candidate.id, candidate]))
  const latestInterviewsByCandidate = new Map()

  for (const interview of interviewRows || []) {
    if (!interview?.candidate_id) continue
    const previousInterview = latestInterviewsByCandidate.get(interview.candidate_id)
    const previousDate = previousInterview?.scheduled_at || previousInterview?.created_at || ''
    const currentDate = interview.scheduled_at || interview.created_at || ''
    if (!previousInterview || new Date(currentDate) > new Date(previousDate)) {
      latestInterviewsByCandidate.set(interview.candidate_id, interview)
    }
  }

  const pipelineDisplayCandidates = (candidatesData || [])
    .map((candidate) => ({
      ...candidate,
      display_stage: resolveDashboardDisplayStage(candidate, latestInterviewsByCandidate.get(candidate.id)),
    }))

  const shortlistedPipelineCandidates = pipelineDisplayCandidates
    .filter((candidate) => candidate.display_stage === 'SHORTLISTED')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))

  const mapInterviewCandidates = (predicate, getDisplayStage) => Array.from(latestInterviewsByCandidate.values())
    .filter(predicate)
    .map((interview) => {
      const candidate = candidateMap.get(interview.candidate_id)
      if (!candidate) return null

      return {
        ...candidate,
        display_score: interview?.interview_score,
        display_stage: getDisplayStage(interview),
        rejected_at: interview?.scheduled_at || interview?.created_at || candidate.created_at,
      }
    })
    .filter(Boolean)
    .sort((a, b) => new Date(b.rejected_at) - new Date(a.rejected_at))

  const activeInterviewCandidates = mapInterviewCandidates((interview) => {
    const status = (interview?.status || '').toLowerCase()
    return status === 'scheduled' || status === 'ongoing'
  }, (interview) => ((interview?.status || '').toLowerCase() === 'scheduled' ? 'INTERVIEW_SCHEDULED' : 'INTERVIEW'))

  const selectedCandidates = mapInterviewCandidates((interview) => {
    const status = (interview?.status || '').toLowerCase()
    return status === 'completed' && Number(interview?.interview_score) >= INTERVIEW_REJECTION_SCORE_THRESHOLD
  }, () => 'SELECTED')

  const rejectedCandidates = mapInterviewCandidates((interview) => {
    const status = (interview?.status || '').toLowerCase()
    return status === 'completed' && Number(interview?.interview_score) < INTERVIEW_REJECTION_SCORE_THRESHOLD
  }, () => 'REJECTED')

  return {
    totalCandidates: pipelineDisplayCandidates,
    shortlistedCandidates: shortlistedPipelineCandidates,
    interviewCandidates: activeInterviewCandidates,
    selectedInterviewCandidates: selectedCandidates,
    interviewRejectedCandidates: rejectedCandidates,
  }
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const [selectedMonth, setSelectedMonth] = useState('all')
  const [selectedDate, setSelectedDate] = useState(null)
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear())
  const [selectedMonthNum, setSelectedMonthNum] = useState(null)
  const [selectedCard, setSelectedCard] = useState(null)
  const [cardCandidates, setCardCandidates] = useState([])
  const [cardLoading, setCardLoading] = useState(false)
  const [lazyCardData, setLazyCardData] = useState(null)
  const [shouldLoadDashboardDetails, setShouldLoadDashboardDetails] = useState(false)
  const [shouldLoadDeferredAnalytics, setShouldLoadDeferredAnalytics] = useState(false)
  const [showLowCreditModal, setShowLowCreditModal] = useState(false)
  const [lowCreditDismissed, setLowCreditDismissed] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.sessionStorage.getItem(LOW_CREDIT_MODAL_DISMISSED_KEY) === 'true'
  })

  const dashboardParams = useMemo(() => {
    const params = {}
    if (selectedClient) params.client = selectedClient
    if (selectedDate) {
      params.date = selectedDate
    } else if (selectedMonth !== 'all') {
      params.month = selectedMonth
    }
    return params
  }, [selectedClient, selectedDate, selectedMonth])

  const statsQuery = useQuery({
    queryKey: ['dashboard-overview-stats', dashboardParams],
    queryFn: async () => {
      return api.getDashboardStats(dashboardParams).catch((error) => {
        console.error('Stats error:', error)
        return null
      })
    },
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
  })

  const detailsQuery = useQuery({
    queryKey: ['dashboard-overview-details', dashboardParams],
    enabled: shouldLoadDashboardDetails,
    queryFn: async () => {
      const [activeJobs, upcomingInterviews, hiringMetrics, intelligence] = await Promise.all([
        api.getActiveJobs().catch((error) => {
          console.error('Jobs error:', error)
          return []
        }),
        api.getUpcomingInterviews().catch((error) => {
          console.error('Interviews error:', error)
          return []
        }),
        api.getHiringMetrics().catch((error) => {
          console.error('Metrics error:', error)
          return null
        }),
        api.getHiringIntelligence().catch((error) => {
          console.error('Intelligence error:', error)
          return null
        }),
      ])

      return { activeJobs, upcomingInterviews, hiringMetrics, intelligence }
    },
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
  })

  const deferredAnalyticsQuery = useQuery({
    queryKey: ['dashboard-overview-deferred', dashboardParams],
    enabled: shouldLoadDeferredAnalytics,
    queryFn: async () => {
      const [resumeTrend, interviewTrend] = await Promise.all([
        api.getResumeScoresTrend().catch((error) => {
          console.error('Resume trend error:', error)
          return []
        }),
        api.getInterviewScoresTrend().catch((error) => {
          console.error('Interview trend error:', error)
          return []
        }),
      ])

      return { resumeTrend, interviewTrend }
    },
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
  })

  const stats = statsQuery.data || null
  const activeJobs = detailsQuery.data?.activeJobs || []
  const upcomingInterviews = detailsQuery.data?.upcomingInterviews || []
  const hiringMetrics = detailsQuery.data?.hiringMetrics || null
  const intelligence = detailsQuery.data?.intelligence || null
  const resumeTrend = deferredAnalyticsQuery.data?.resumeTrend || []
  const interviewTrend = deferredAnalyticsQuery.data?.interviewTrend || []
  const loading = statsQuery.isLoading && !statsQuery.data


  // Force close modal on mount and prevent any stuck state
  useEffect(() => {
    setSelectedCard(null)
    setCardCandidates([])
    setCardLoading(false)
  }, [])

  useEffect(() => {
    setShouldLoadDashboardDetails(false)
    setShouldLoadDeferredAnalytics(false)
    setLazyCardData(null)
  }, [dashboardParams])

  useEffect(() => {
    if (!statsQuery.isSuccess) return undefined

    let cancelled = false
    const loadDashboardDetails = () => {
      if (!cancelled) {
        setShouldLoadDashboardDetails(true)
      }
    }

    if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
      const idleId = window.requestIdleCallback(loadDashboardDetails, { timeout: 300 })
      return () => {
        cancelled = true
        window.cancelIdleCallback(idleId)
      }
    }

    const timeoutId = window.setTimeout(loadDashboardDetails, 150)
    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [statsQuery.isSuccess, dashboardParams])

  useEffect(() => {
    if (!detailsQuery.isSuccess) return undefined

    let cancelled = false
    const loadDeferredAnalytics = () => {
      if (!cancelled) {
        setShouldLoadDeferredAnalytics(true)
      }
    }

    if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
      const idleId = window.requestIdleCallback(loadDeferredAnalytics, { timeout: 500 })
      return () => {
        cancelled = true
        window.cancelIdleCallback(idleId)
      }
    }

    const timeoutId = window.setTimeout(loadDeferredAnalytics, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [detailsQuery.isSuccess, dashboardParams])

  useEffect(() => {
    if (user?.role === 'admin' && typeof user?.wallet_balance === 'number' && user.wallet_balance <= 10) {
      setShowLowCreditModal(!lowCreditDismissed)
    } else {
      setShowLowCreditModal(false)
      if (typeof window !== 'undefined') {
        window.sessionStorage.removeItem(LOW_CREDIT_MODAL_DISMISSED_KEY)
      }
      if (lowCreditDismissed) {
        setLowCreditDismissed(false)
      }
    }
  }, [lowCreditDismissed, user])

  const dismissLowCreditModal = () => {
    setShowLowCreditModal(false)
    setLowCreditDismissed(true)
    if (typeof window !== 'undefined') {
      window.sessionStorage.setItem(LOW_CREDIT_MODAL_DISMISSED_KEY, 'true')
    }
  }

  const kpiCards = stats ? [
    { title: 'Total Candidates', value: stats.total_candidates || 0, icon: Users, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30', filter: {} },
    { title: 'Shortlisted', value: stats.shortlisted || 0, icon: UserCheck, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/30', filter: { type: 'pipeline_shortlisted' } },
    { title: 'Interviews', value: stats.interviews_scheduled || 0, icon: Calendar, color: 'text-orange-600', bg: 'bg-orange-100 dark:bg-orange-900/30', filter: { type: 'interview_active' } },
    { title: 'Selected', value: stats.selected || 0, icon: Award, color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30', filter: { type: 'interview_selected' } },
    { title: 'Rejected', value: stats.rejected || 0, icon: UserX, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30', filter: { type: 'interview_rejected' } },
  ] : [
    { title: 'Total Candidates', value: 0, icon: Users, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30', filter: {} },
    { title: 'Shortlisted', value: 0, icon: UserCheck, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/30', filter: { type: 'pipeline_shortlisted' } },
    { title: 'Interviews', value: 0, icon: Calendar, color: 'text-orange-600', bg: 'bg-orange-100 dark:bg-orange-900/30', filter: { type: 'interview_active' } },
    { title: 'Selected', value: 0, icon: Award, color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30', filter: { type: 'interview_selected' } },
    { title: 'Rejected', value: 0, icon: UserX, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30', filter: { type: 'interview_rejected' } },
  ]

  const loadCardBuckets = useCallback(async () => {
    if (lazyCardData) {
      return lazyCardData
    }

    const [candidatesData, interviewRows] = await Promise.all([
      api.getCandidates({ ...dashboardParams, limit: 20, offset: 0 }).catch((error) => {
        console.error('Candidates error:', error)
        return []
      }),
      api.getInterviews({ limit: 20, offset: 0 }).catch((error) => {
        console.error('Interviews list error:', error)
        return []
      }),
    ])

    const nextBuckets = buildDashboardCandidateBuckets(candidatesData, interviewRows)
    setLazyCardData(nextBuckets)
    return nextBuckets
  }, [dashboardParams, lazyCardData])

  const handleCardClick = useCallback(async (card) => {
    setSelectedCard(card)
    setCardLoading(true)
    try {
      if (
        card.title === 'Total Candidates'
        || card.filter?.type === 'pipeline_shortlisted'
        || card.filter?.type === 'interview_active'
        || card.filter?.type === 'interview_selected'
        || card.filter?.type === 'interview_rejected'
      ) {
        const buckets = await loadCardBuckets()

        if (card.title === 'Total Candidates') {
          setCardCandidates(buckets.totalCandidates)
          return
        }

        if (card.filter?.type === 'pipeline_shortlisted') {
          setCardCandidates(buckets.shortlistedCandidates)
          return
        }

        if (card.filter?.type === 'interview_active') {
          setCardCandidates(buckets.interviewCandidates)
          return
        }

        if (card.filter?.type === 'interview_selected') {
          setCardCandidates(buckets.selectedInterviewCandidates)
          return
        }

        if (card.filter?.type === 'interview_rejected') {
          setCardCandidates(buckets.interviewRejectedCandidates)
          return
        }
      }

      const filter = { ...card.filter }
      if (selectedClient) {
        filter.client = selectedClient
      }
      if (selectedDate) {
        filter.date = selectedDate
      } else if (selectedMonth !== 'all') {
        filter.month = selectedMonth
      }
      
      // Handle multiple stages filter
      if (filter.stages && filter.stages.length > 0) {
        // Fetch candidates for each stage and combine
        const allCandidates = []
        for (const stage of filter.stages) {
          const stageFilter = { ...filter, stage }
          delete stageFilter.stages
          const candidates = await api.getCandidates(stageFilter)
          allCandidates.push(...(candidates || []))
        }
        setCardCandidates(allCandidates)
      } else {
        const candidates = await api.getCandidates(filter)
        setCardCandidates(candidates || [])
      }
    } catch (error) {
      console.error('Failed to fetch card candidates:', error)
      setCardCandidates([])
    } finally {
      setCardLoading(false)
    }
  }, [dashboardParams, loadCardBuckets, selectedClient, selectedDate, selectedMonth])

  const closeModal = () => {
    console.log('Closing modal')
    setSelectedCard(null)
    setCardCandidates([])
  }

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        closeModal()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [])

  const handleDateSelect = (day) => {
    if (selectedMonthNum !== null) {
      const dateStr = `${selectedYear}-${String(selectedMonthNum).padStart(2, '0')}-${String(day).padStart(2, '0')}`
      setSelectedDate(dateStr)
      setSelectedMonth('all')
      setCalendarOpen(false)
    }
  }

  const handleMonthSelect = (month) => {
    setSelectedMonthNum(month)
  }

  const applyMonthFilter = () => {
    if (selectedMonthNum !== null) {
      const monthStr = `${selectedYear}-${String(selectedMonthNum).padStart(2, '0')}`
      setSelectedMonth(monthStr)
      setSelectedDate(null)
      setCalendarOpen(false)
    }
  }

  const handleYearChange = (direction) => {
    setSelectedYear(prev => prev + direction)
    setSelectedMonthNum(null)
  }

  const clearFilter = () => {
    setSelectedDate(null)
    setSelectedMonth('all')
    setSelectedMonthNum(null)
  }



  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  
  const getDaysInMonth = (year, month) => {
    return new Date(year, month, 0).getDate()
  }

  const getFilterLabel = () => {
    if (selectedDate) {
      return new Date(selectedDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
    }
    if (selectedMonth !== 'all') {
      const [year, month] = selectedMonth.split('-')
      return new Date(year, parseInt(month) - 1).toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
    }
    return 'Select Date'
  }

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
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">Overview of your recruitment pipeline</p>
        </div>
        <div className="flex items-center gap-2">
          <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
            <PopoverTrigger asChild>
              <Button variant="outline" className="w-[240px] justify-start text-left font-normal">
                <CalendarIcon className="mr-2 h-4 w-4" />
                {getFilterLabel()}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="end">
              <div className="p-3">
                {/* Year Selector */}
                <div className="flex items-center justify-between mb-3">
                  <Button variant="outline" size="sm" onClick={() => handleYearChange(-1)}>←</Button>
                  <span className="font-semibold">{selectedYear}</span>
                  <Button variant="outline" size="sm" onClick={() => handleYearChange(1)}>→</Button>
                </div>
                
                {/* Month Selector */}
                {selectedMonthNum === null ? (
                  <div className="grid grid-cols-3 gap-2">
                    {monthNames.map((month, idx) => (
                      <Button
                        key={idx}
                        variant="outline"
                        size="sm"
                        onClick={() => handleMonthSelect(idx + 1)}
                        className="h-9"
                      >
                        {month}
                      </Button>
                    ))}
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Button variant="ghost" size="sm" onClick={() => setSelectedMonthNum(null)}>← Back</Button>
                      <span className="font-medium">{monthNames[selectedMonthNum - 1]} {selectedYear}</span>
                    </div>
                    
                    {/* Option to select entire month or specific date */}
                    <div className="mb-3 flex gap-2">
                      <Button
                        variant="default"
                        size="sm"
                        onClick={applyMonthFilter}
                        className="flex-1"
                      >
                        Entire Month
                      </Button>
                      <span className="text-xs text-muted-foreground self-center">or select a date below</span>
                    </div>
                    
                    <div className="grid grid-cols-7 gap-1">
                      {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, idx) => (
                        <div key={idx} className="text-center text-xs font-medium text-muted-foreground p-1">{day}</div>
                      ))}
                      {Array.from({ length: getDaysInMonth(selectedYear, selectedMonthNum) }, (_, i) => i + 1).map(day => (
                        <Button
                          key={day}
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDateSelect(day)}
                          className="h-8 w-8 p-0"
                        >
                          {day}
                        </Button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </PopoverContent>
          </Popover>
          {(selectedDate || selectedMonth !== 'all') && (
            <Button variant="ghost" size="sm" onClick={clearFilter}>
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="sticky top-0 z-20 -mx-2 bg-background/95 px-2 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          {kpiCards.map((kpi) => (
            <Card key={kpi.title} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => handleCardClick(kpi)}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{kpi.title}</p>
                    <p className="text-3xl font-bold mt-1">{kpi.value}</p>
                  </div>
                  <div className={cn('p-3 rounded-xl', kpi.bg)}>
                    <kpi.icon className={cn('h-6 w-6', kpi.color)} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Hiring Intelligence Card */}
      {intelligence && intelligence.insights && intelligence.insights.length > 0 && (
        <HiringIntelligence insights={intelligence.insights} />
      )}

      {/* Active Jobs & Upcoming Interviews */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Active Jobs */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Active Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-[300px] overflow-y-auto">
              {activeJobs && activeJobs.length > 0 ? (
                activeJobs.map((job) => (
                  <div key={job.id} className="flex items-start justify-between p-3 border rounded-lg">
                    <div className="flex-1">
                      <p className="font-medium">{job.title} - {job.company_name || 'N/A'}</p>
                      <p className="text-xs text-muted-foreground mt-1">{job.department || 'N/A'}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className="text-sm font-medium">{job.candidates || 0} {job.candidates === 1 ? 'candidate' : 'candidates'}</p>
                        <p className="text-xs text-muted-foreground">{job.vacancies || 1} {(job.vacancies || 1) === 1 ? 'position' : 'positions'}</p>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Briefcase className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>No active jobs</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Upcoming Interviews */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Upcoming Interviews</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-[300px] overflow-y-auto">
              {upcomingInterviews.length > 0 ? (
                upcomingInterviews.map((interview) => (
                  <div key={interview.id} className="p-3 border rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <Calendar className="h-5 w-5 text-primary" />
                      </div>
                      <div className="flex-1">
                        <p className="font-medium">{interview.candidate_name}</p>
                        <p className="text-xs text-muted-foreground capitalize">
                          {interview.interview_type}
                          {interview.job_title ? ` • ${interview.job_title}` : ''}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">
                          {interview.scheduled_at ? new Date(interview.scheduled_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'TBD'}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {interview.scheduled_at ? new Date(interview.scheduled_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : ''}
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Clock className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>No upcoming interviews</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Resume Score Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Resume Score Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={resumeTrend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="month" className="text-xs" />
                  <YAxis domain={[0, 100]} className="text-xs" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'hsl(var(--card))', 
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }} 
                  />
                  <Line 
                    type="monotone" 
                    dataKey="avg_score" 
                    stroke="hsl(var(--primary))" 
                    strokeWidth={2}
                    dot={{ fill: 'hsl(var(--primary))' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Interview Score Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Interview Scores Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={interviewTrend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="month" className="text-xs" />
                  <YAxis domain={[0, 100]} className="text-xs" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'hsl(var(--card))', 
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }} 
                  />
                  <Bar dataKey="technical" fill="#3b82f6" name="Technical" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="communication" fill="#8b5cf6" name="Communication" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Modal for Card Details */}
      {selectedCard && selectedCard.title && cardCandidates !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={closeModal}>
          <div className="bg-card rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">{selectedCard.title} Details</h2>
              <Button variant="ghost" size="icon" onClick={closeModal}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            {cardLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-muted-foreground">Total: {cardCandidates.length} candidates</p>
                
                {cardCandidates.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="text-left p-3 font-medium">Name</th>
                          <th className="text-left p-3 font-medium">Email</th>
                          <th className="text-left p-3 font-medium">Job</th>
                          <th className="text-left p-3 font-medium">Score</th>
                          <th className="text-left p-3 font-medium">Stage</th>
                          <th className="text-left p-3 font-medium">Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cardCandidates.map((candidate) => (
                          <tr key={candidate.id} className="border-b hover:bg-muted/50">
                            <td className="p-3 font-medium">{candidate.name}</td>
                            <td className="p-3 text-sm text-muted-foreground">{candidate.email}</td>
                            <td className="p-3 text-sm">{candidate.job_title || '-'}</td>
                            <td className="p-3">
                              {((candidate.display_score !== undefined && candidate.display_score !== null)
                                || (candidate.resume_score !== undefined && candidate.resume_score !== null)) ? (
                                <span className={cn('font-semibold', getScoreColor(candidate.display_score ?? candidate.resume_score))}>
                                  {candidate.display_score ?? candidate.resume_score}
                                </span>
                              ) : (
                                <span className="text-muted-foreground">-</span>
                              )}
                            </td>
                            <td className="p-3">
                              <Badge variant="outline" className="capitalize">
                                {(candidate.display_stage || candidate.stage).replaceAll('_', ' ')}
                              </Badge>
                            </td>
                            <td className="p-3 text-sm text-muted-foreground">
                              {formatDate(candidate.rejected_at || candidate.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No candidates found for this category
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {showLowCreditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-card rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-yellow-100 p-2 rounded-full">
                <DollarSign className="h-6 w-6 text-yellow-600" />
              </div>
              <h2 className="text-lg font-bold">Low Credits Warning</h2>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              Your credits are low, to continue the service do recharge.
            </p>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1" onClick={dismissLowCreditModal}>
                Cancel
              </Button>
              <Button className="flex-1" onClick={() => navigate('/wallet?lowCredits=1')}>
                Proceed to Payment
              </Button>
            </div>
          </div>
        </div>
      )}


    </div>
  )
}


