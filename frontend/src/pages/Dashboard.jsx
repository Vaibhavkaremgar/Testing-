import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { cn, getScoreColor, formatDate } from '@/lib/utils'
import {
  Users, UserCheck, UserX, Calendar, Award, TrendingUp, FileText, X, CalendarIcon, Briefcase, Clock, CheckCircle
} from 'lucide-react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, FunnelChart, Funnel, LabelList, Cell, PieChart, Pie
} from 'recharts'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

const COLORS = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b']

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [funnel, setFunnel] = useState([])
  const [resumeTrend, setResumeTrend] = useState([])
  const [interviewTrend, setInterviewTrend] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedMonth, setSelectedMonth] = useState('all')
  const [selectedDate, setSelectedDate] = useState(null)
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear())
  const [selectedMonthNum, setSelectedMonthNum] = useState(null)
  const [activeJobs, setActiveJobs] = useState([])
  const [upcomingInterviews, setUpcomingInterviews] = useState([])
  const [selectedCard, setSelectedCard] = useState(null)
  const [cardCandidates, setCardCandidates] = useState([])
  const [cardLoading, setCardLoading] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const params = {}
        if (selectedDate) {
          params.date = selectedDate
        } else if (selectedMonth !== 'all') {
          params.month = selectedMonth
        }
        const [statsData, funnelData, resumeData, interviewData, jobs, interviews] = await Promise.all([
          api.getDashboardStats(params).catch(e => { console.error('Stats error:', e); return null; }),
          api.getHiringFunnel(params).catch(e => { console.error('Funnel error:', e); return []; }),
          api.getResumeScoresTrend().catch(e => { console.error('Resume trend error:', e); return []; }),
          api.getInterviewScoresTrend().catch(e => { console.error('Interview trend error:', e); return []; }),
          api.getActiveJobs().catch(e => { console.error('Jobs error:', e); return []; }),
          api.getUpcomingInterviews().catch(e => { console.error('Interviews error:', e); return []; })
        ])
        setStats(statsData)
        setFunnel(funnelData)
        setResumeTrend(resumeData)
        setInterviewTrend(interviewData)
        setActiveJobs(jobs)
        setUpcomingInterviews(interviews)
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [selectedMonth, selectedDate])

  const kpiCards = stats ? [
    { title: 'Total Candidates', value: stats.total_candidates, icon: Users, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30', filter: {} },
    { title: 'Shortlisted', value: stats.shortlisted, icon: UserCheck, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/30', filter: { stage: 'shortlisted' } },
    { title: 'Interviews', value: stats.interviews_scheduled, icon: Calendar, color: 'text-orange-600', bg: 'bg-orange-100 dark:bg-orange-900/30', filter: { stage: 'interview_scheduled' } },
    { title: 'Selected', value: stats.selected, icon: Award, color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30', filter: { stage: 'selected' } },
    { title: 'Rejected', value: stats.rejected, icon: UserX, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30', filter: { stage: 'rejected' } },
  ] : []

  const handleCardClick = async (card) => {
    setSelectedCard(card)
    setCardLoading(true)
    try {
      const filter = { ...card.filter }
      if (selectedDate) {
        filter.date = selectedDate
      } else if (selectedMonth !== 'all') {
        filter.month = selectedMonth
      }
      const candidates = await api.getCandidates(filter)
      setCardCandidates(candidates || [])
    } catch (error) {
      console.error('Failed to fetch card candidates:', error)
      setCardCandidates([])
    } finally {
      setCardLoading(false)
    }
  }

  const closeModal = () => {
    setSelectedCard(null)
    setCardCandidates([])
  }

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

      {/* Score Card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-primary/10">
              <TrendingUp className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Avg. Interview Score</p>
              <p className={cn('text-3xl font-bold', getScoreColor(stats?.avg_interview_score))}>
                {stats?.avg_interview_score?.toFixed(1)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

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

      {/* Hiring Funnel */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Hiring Funnel</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <FunnelChart>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'hsl(var(--card))', 
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px'
                  }} 
                />
                <Funnel
                  dataKey="count"
                  data={funnel}
                  isAnimationActive
                >
                  {funnel.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                  <LabelList position="right" fill="#888" stroke="none" dataKey="stage" />
                  <LabelList position="center" fill="#fff" stroke="none" dataKey="count" />
                </Funnel>
              </FunnelChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

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
                  <div key={job.id} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex-1">
                      <p className="font-medium">{job.title}</p>
                      <p className="text-xs text-muted-foreground">{job.department || 'N/A'}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className="text-sm font-medium">{job.candidates || 0} candidates</p>
                        <p className="text-xs text-muted-foreground">{job.vacancies || 1} positions</p>
                      </div>
                      <Badge 
                        variant={job.status === 'open' ? 'default' : job.status === 'filled' ? 'secondary' : 'outline'}
                        className="capitalize"
                      >
                        {job.status || 'open'}
                      </Badge>
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
                  <div key={interview.id} className="flex items-center gap-3 p-3 border rounded-lg">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Calendar className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium">{interview.candidate_name}</p>
                      <p className="text-xs text-muted-foreground capitalize">{interview.interview_type}</p>
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

      {/* Modal for Card Details */}
      {selectedCard && (
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
                              {candidate.resume_score ? (
                                <span className={cn('font-semibold', getScoreColor(candidate.resume_score))}>
                                  {candidate.resume_score}
                                </span>
                              ) : (
                                <span className="text-muted-foreground">-</span>
                              )}
                            </td>
                            <td className="p-3">
                              <Badge variant="outline" className="capitalize">
                                {candidate.stage.replace('_', ' ')}
                              </Badge>
                            </td>
                            <td className="p-3 text-sm text-muted-foreground">
                              {formatDate(candidate.created_at)}
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


    </div>
  )
}
