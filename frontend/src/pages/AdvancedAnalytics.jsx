import { useState, useEffect, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area
} from 'recharts'
import {
  Calendar, Filter, TrendingUp, Award, Clock, Target, Users, Zap, Trophy, Star
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const COLORS = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

export default function AdvancedAnalytics() {
  // Filter states
  const [dateRange, setDateRange] = useState('30')
  const [customStartDate, setCustomStartDate] = useState('')
  const [customEndDate, setCustomEndDate] = useState('')
  const [selectedClients, setSelectedClients] = useState([])
  const [selectedRecruiters, setSelectedRecruiters] = useState([])
  const [selectedDepartments, setSelectedDepartments] = useState([])
  const [selectedJobRoles, setSelectedJobRoles] = useState([])
  const [scoreRange, setScoreRange] = useState([0, 100])

  // Data states
  const [candidates, setCandidates] = useState([])
  const [jobs, setJobs] = useState([])
  const [interviews, setInterviews] = useState([])
  const [users, setUsers] = useState([])
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)

  // Recruiter performance sort
  const [sortBy, setSortBy] = useState('timeToHire')
  const [sortOrder, setSortOrder] = useState('asc')

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [candidatesData, jobsData, interviewsData, usersData, clientsData] = await Promise.all([
        api.getCandidates(),
        api.getJobs(),
        api.getInterviews(),
        api.getPublicUsers(),
        api.getClients()
      ])
      setCandidates(candidatesData || [])
      setJobs(jobsData || [])
      setInterviews(interviewsData || [])
      setUsers(usersData || [])
      setClients(clientsData || [])
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }

  // Filter data based on selections
  const filteredData = useMemo(() => {
    let filtered = candidates

    // Date range filter
    if (dateRange !== 'all') {
      const now = new Date()
      let startDate = new Date()
      
      if (dateRange === 'custom') {
        if (customStartDate) startDate = new Date(customStartDate)
        if (customEndDate) {
          const endDate = new Date(customEndDate)
          filtered = filtered.filter(c => {
            const createdDate = new Date(c.created_at)
            return createdDate >= startDate && createdDate <= endDate
          })
        }
      } else {
        const days = parseInt(dateRange)
        startDate.setDate(now.getDate() - days)
        filtered = filtered.filter(c => new Date(c.created_at) >= startDate)
      }
    }

    // Client filter
    if (selectedClients.length > 0) {
      filtered = filtered.filter(c => selectedClients.includes(c.client_id?.toString()))
    }

    // Recruiter filter
    if (selectedRecruiters.length > 0) {
      filtered = filtered.filter(c => selectedRecruiters.includes(c.assigned_to_user_id?.toString()))
    }

    // Department filter
    if (selectedDepartments.length > 0) {
      const jobsInDept = jobs.filter(j => selectedDepartments.includes(j.department))
      const jobIds = jobsInDept.map(j => j.id)
      filtered = filtered.filter(c => jobIds.includes(c.job_id))
    }

    // Job role filter
    if (selectedJobRoles.length > 0) {
      filtered = filtered.filter(c => selectedJobRoles.includes(c.job_id?.toString()))
    }

    // Score range filter
    filtered = filtered.filter(c => {
      const score = c.resume_score || 0
      return score >= scoreRange[0] && score <= scoreRange[1]
    })

    return filtered
  }, [candidates, dateRange, customStartDate, customEndDate, selectedClients, selectedRecruiters, selectedDepartments, selectedJobRoles, scoreRange, jobs])

  // Calculate recruiter performance metrics
  const recruiterPerformance = useMemo(() => {
    const recruiterMap = {}

    users.forEach(user => {
      const userCandidates = filteredData.filter(c => c.assigned_to_user_id === user.id)
      const userInterviews = interviews.filter(i => 
        userCandidates.some(c => c.id === i.candidate_id)
      )

      const selectedCandidates = userCandidates.filter(c => c.stage === 'SELECTED')
      const interviewedCandidates = userCandidates.filter(c => c.stage === 'INTERVIEWED' || c.stage === 'SELECTED')
      const offeredCandidates = userCandidates.filter(c => c.stage === 'SELECTED')

      // Calculate time to hire (days from created to selected)
      const timeToHireValues = selectedCandidates.map(c => {
        const created = new Date(c.created_at)
        const updated = new Date(c.updated_at)
        return Math.floor((updated - created) / (1000 * 60 * 60 * 24))
      })
      const avgTimeToHire = timeToHireValues.length > 0 
        ? timeToHireValues.reduce((a, b) => a + b, 0) / timeToHireValues.length 
        : 0

      // Interview to offer conversion
      const interviewToOfferRate = interviewedCandidates.length > 0
        ? (offeredCandidates.length / interviewedCandidates.length) * 100
        : 0

      // Offer acceptance rate (assuming selected = accepted)
      const offerAcceptanceRate = offeredCandidates.length > 0 ? 100 : 0

      // Average resume score
      const scores = userCandidates.map(c => c.resume_score || 0).filter(s => s > 0)
      const avgScore = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0

      // Active pipeline
      const activePipeline = userCandidates.filter(c => 
        !['REJECTED', 'SELECTED', 'RESUME_REJECTED'].includes(c.stage)
      ).length

      recruiterMap[user.id] = {
        id: user.id,
        name: user.full_name,
        email: user.email,
        avgTimeToHire: Math.round(avgTimeToHire),
        interviewToOfferRate: Math.round(interviewToOfferRate),
        offerAcceptanceRate: Math.round(offerAcceptanceRate),
        candidatesProcessed: userCandidates.length,
        avgResumeScore: Math.round(avgScore),
        activePipeline,
        selectedCount: selectedCandidates.length
      }
    })

    return Object.values(recruiterMap).filter(r => r.candidatesProcessed > 0)
  }, [filteredData, users, interviews])

  // Sort recruiter performance
  const sortedRecruiters = useMemo(() => {
    const sorted = [...recruiterPerformance].sort((a, b) => {
      let aVal = a[sortBy]
      let bVal = b[sortBy]
      
      if (sortBy === 'avgTimeToHire') {
        // Lower is better for time to hire
        return sortOrder === 'asc' ? aVal - bVal : bVal - aVal
      }
      
      return sortOrder === 'asc' ? aVal - bVal : bVal - aVal
    })
    return sorted
  }, [recruiterPerformance, sortBy, sortOrder])

  // Assign badges
  const getBadges = (recruiter, index) => {
    const badges = []
    
    if (index === 0 && sortBy === 'avgTimeToHire' && sortOrder === 'asc') {
      badges.push({ label: 'Fastest Closer', color: 'bg-yellow-500', icon: Zap })
    }
    if (index === 0 && sortBy === 'avgResumeScore' && sortOrder === 'desc') {
      badges.push({ label: 'Quality Screener', color: 'bg-purple-500', icon: Star })
    }
    if (index === 0 && sortBy === 'selectedCount' && sortOrder === 'desc') {
      badges.push({ label: 'Top Performer', color: 'bg-green-500', icon: Trophy })
    }
    if (recruiter.interviewToOfferRate >= 80) {
      badges.push({ label: 'High Converter', color: 'bg-blue-500', icon: Target })
    }
    
    return badges
  }

  // Get unique values for filters
  const uniqueDepartments = [...new Set(jobs.map(j => j.department).filter(Boolean))]
  const uniqueJobRoles = jobs.filter(j => j.title)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Advanced Analytics</h1>
        <p className="text-muted-foreground">Enterprise-grade recruitment insights</p>
      </div>

      {/* Global Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Global Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Date Range */}
            <div>
              <label className="text-sm font-medium mb-2 block">Date Range</label>
              <select
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="7">Last 7 days</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last Quarter</option>
                <option value="365">Last Year</option>
                <option value="all">All Time</option>
                <option value="custom">Custom Range</option>
              </select>
              {dateRange === 'custom' && (
                <div className="mt-2 space-y-2">
                  <Input
                    type="date"
                    value={customStartDate}
                    onChange={(e) => setCustomStartDate(e.target.value)}
                    placeholder="Start date"
                  />
                  <Input
                    type="date"
                    value={customEndDate}
                    onChange={(e) => setCustomEndDate(e.target.value)}
                    placeholder="End date"
                  />
                </div>
              )}
            </div>

            {/* Client Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">Client</label>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="w-full justify-start">
                    {selectedClients.length > 0 ? `${selectedClients.length} selected` : 'All Clients'}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56">
                  {clients.map(client => (
                    <DropdownMenuCheckboxItem
                      key={client.id}
                      checked={selectedClients.includes(client.id.toString())}
                      onCheckedChange={(checked) => {
                        setSelectedClients(prev =>
                          checked ? [...prev, client.id.toString()] : prev.filter(id => id !== client.id.toString())
                        )
                      }}
                    >
                      {client.name}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Recruiter Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">Recruiter</label>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="w-full justify-start">
                    {selectedRecruiters.length > 0 ? `${selectedRecruiters.length} selected` : 'All Recruiters'}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56">
                  {users.map(user => (
                    <DropdownMenuCheckboxItem
                      key={user.id}
                      checked={selectedRecruiters.includes(user.id.toString())}
                      onCheckedChange={(checked) => {
                        setSelectedRecruiters(prev =>
                          checked ? [...prev, user.id.toString()] : prev.filter(id => id !== user.id.toString())
                        )
                      }}
                    >
                      {user.full_name}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Department Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">Department</label>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="w-full justify-start">
                    {selectedDepartments.length > 0 ? `${selectedDepartments.length} selected` : 'All Departments'}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56">
                  {uniqueDepartments.map(dept => (
                    <DropdownMenuCheckboxItem
                      key={dept}
                      checked={selectedDepartments.includes(dept)}
                      onCheckedChange={(checked) => {
                        setSelectedDepartments(prev =>
                          checked ? [...prev, dept] : prev.filter(d => d !== dept)
                        )
                      }}
                    >
                      {dept}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Job Role Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">Job Role</label>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="w-full justify-start">
                    {selectedJobRoles.length > 0 ? `${selectedJobRoles.length} selected` : 'All Roles'}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56">
                  {uniqueJobRoles.map(job => (
                    <DropdownMenuCheckboxItem
                      key={job.id}
                      checked={selectedJobRoles.includes(job.id.toString())}
                      onCheckedChange={(checked) => {
                        setSelectedJobRoles(prev =>
                          checked ? [...prev, job.id.toString()] : prev.filter(id => id !== job.id.toString())
                        )
                      }}
                    >
                      {job.title}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Score Range */}
            <div>
              <label className="text-sm font-medium mb-2 block">
                Resume Score: {scoreRange[0]} - {scoreRange[1]}
              </label>
              <div className="flex gap-2 items-center">
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={scoreRange[0]}
                  onChange={(e) => setScoreRange([parseInt(e.target.value), scoreRange[1]])}
                  className="w-20"
                />
                <span>-</span>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={scoreRange[1]}
                  onChange={(e) => setScoreRange([scoreRange[0], parseInt(e.target.value)])}
                  className="w-20"
                />
              </div>
            </div>

            {/* Clear Filters */}
            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={() => {
                  setDateRange('30')
                  setSelectedClients([])
                  setSelectedRecruiters([])
                  setSelectedDepartments([])
                  setSelectedJobRoles([])
                  setScoreRange([0, 100])
                }}
                className="w-full"
              >
                Clear All Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recruiter Performance Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Users className="h-5 w-5" />
              Recruiter Performance Leaderboard
            </CardTitle>
            <div className="flex gap-2">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="rounded-lg border border-input bg-background px-3 py-1 text-sm"
              >
                <option value="avgTimeToHire">Time to Hire</option>
                <option value="interviewToOfferRate">Conversion Rate</option>
                <option value="offerAcceptanceRate">Acceptance Rate</option>
                <option value="candidatesProcessed">Candidates Processed</option>
                <option value="avgResumeScore">Avg Score</option>
                <option value="activePipeline">Active Pipeline</option>
                <option value="selectedCount">Hires Made</option>
              </select>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              >
                {sortOrder === 'asc' ? '↑' : '↓'}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {sortedRecruiters.map((recruiter, index) => {
              const badges = getBadges(recruiter, index)
              return (
                <div
                  key={recruiter.id}
                  className={cn(
                    "p-4 rounded-lg border",
                    index === 0 && "bg-yellow-50 dark:bg-yellow-900/10 border-yellow-200 dark:border-yellow-800",
                    index === 1 && "bg-gray-50 dark:bg-gray-900/10 border-gray-200 dark:border-gray-800",
                    index === 2 && "bg-orange-50 dark:bg-orange-900/10 border-orange-200 dark:border-orange-800"
                  )}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center font-bold",
                        index === 0 && "bg-yellow-500 text-white",
                        index === 1 && "bg-gray-400 text-white",
                        index === 2 && "bg-orange-500 text-white",
                        index > 2 && "bg-muted text-muted-foreground"
                      )}>
                        {index + 1}
                      </div>
                      <div>
                        <p className="font-semibold">{recruiter.name}</p>
                        <p className="text-sm text-muted-foreground">{recruiter.email}</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {badges.map((badge, i) => (
                        <Badge key={i} className={cn(badge.color, "text-white flex items-center gap-1")}>
                          <badge.icon className="h-3 w-3" />
                          {badge.label}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Avg Time to Hire</p>
                      <p className="text-lg font-bold flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        {recruiter.avgTimeToHire}d
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Interview→Offer</p>
                      <p className="text-lg font-bold flex items-center gap-1">
                        <TrendingUp className="h-4 w-4" />
                        {recruiter.interviewToOfferRate}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Acceptance Rate</p>
                      <p className="text-lg font-bold flex items-center gap-1">
                        <Award className="h-4 w-4" />
                        {recruiter.offerAcceptanceRate}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Candidates</p>
                      <p className="text-lg font-bold">{recruiter.candidatesProcessed}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Avg Score</p>
                      <p className="text-lg font-bold">{recruiter.avgResumeScore}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Active Pipeline</p>
                      <p className="text-lg font-bold">{recruiter.activePipeline}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Hires Made</p>
                      <p className="text-lg font-bold text-green-600">{recruiter.selectedCount}</p>
                    </div>
                  </div>
                </div>
              )
            })}
            {sortedRecruiters.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No recruiter data available for the selected filters
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Candidates</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{filteredData.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg Resume Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {filteredData.length > 0
                ? Math.round(filteredData.reduce((sum, c) => sum + (c.resume_score || 0), 0) / filteredData.length)
                : 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Selected</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {filteredData.filter(c => c.stage === 'SELECTED').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {filteredData.filter(c => !['REJECTED', 'SELECTED', 'RESUME_REJECTED'].includes(c.stage)).length}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
