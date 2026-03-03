import { useState, useEffect } from 'react'
import { useAuth } from '@/context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area
} from 'recharts'
import { Settings2 } from 'lucide-react'

const COLORS = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

export default function Analytics() {
  const { user } = useAuth()
  const [timeToHire, setTimeToHire] = useState([])
  const [skillHeatmap, setSkillHeatmap] = useState([])
  const [scoreDistribution, setScoreDistribution] = useState([])
  const [departmentData, setDepartmentData] = useState([])
  const [dateRange, setDateRange] = useState('last_30_days')
  const [customStartDate, setCustomStartDate] = useState('')
  const [customEndDate, setCustomEndDate] = useState('')
  const [compareMode, setCompareMode] = useState(false)
  const [compareType, setCompareType] = useState('previous_period')
  const [selectedClient, setSelectedClient] = useState('all')
  const [selectedRecruiter, setSelectedRecruiter] = useState('all')
  const [clients, setClients] = useState([])
  const [recruiters, setRecruiters] = useState([])
  const [loading, setLoading] = useState(true)
  const isAdmin = user?.role === 'admin'
  const canFilterRecruiters = user?.role === 'admin' || user?.role === 'hiring_manager'

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [timeData, skillData, scoreData, deptData] = await Promise.all([
          api.getTimeToHire(),
          api.getSkillHeatmap(),
          api.getScoreDistribution(),
          api.getHiringByDepartment()
        ])
        setTimeToHire(timeData)
        setSkillHeatmap(skillData)
        setScoreDistribution(scoreData)
        setDepartmentData(deptData)
      } catch (error) {
        console.error('Failed to fetch analytics:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  useEffect(() => {
    const fetchFilterOptions = async () => {
      try {
        const [jobsData, usersData] = await Promise.all([
          api.getJobs({ limit: 1000 }).catch(() => []),
          api.getPublicUsers().catch(() => [])
        ])

        const uniqueClients = Array.from(
          new Set((jobsData || []).map((job) => job.company_name).filter(Boolean))
        ).sort((a, b) => a.localeCompare(b))

        const recruiterUsers = (usersData || []).filter((u) => u?.role === 'recruiter')

        setClients(uniqueClients)
        setRecruiters(recruiterUsers)

        if (user?.role === 'recruiter' && user?.id) {
          setSelectedRecruiter(String(user.id))
        }
      } catch (error) {
        console.error('Failed to fetch analytics filter options:', error)
      }
    }

    fetchFilterOptions()
  }, [user?.id, user?.role])

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
              <Button variant="outline" className="gap-2">
                <Settings2 className="h-4 w-4" />
                Customize Dashboard
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Charts Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Time to Hire */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Time to Hire (Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeToHire}>
                  <defs>
                    <linearGradient id="colorDays" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
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
                  <Area 
                    type="monotone" 
                    dataKey="avg_days" 
                    stroke="#3b82f6" 
                    fillOpacity={1}
                    fill="url(#colorDays)" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Score Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Resume Score Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scoreDistribution}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="range" className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'hsl(var(--card))', 
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }} 
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {scoreDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Hiring by Department */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Hiring by Department</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={departmentData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" className="text-xs" />
                  <YAxis dataKey="department" type="category" className="text-xs" width={80} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'hsl(var(--card))', 
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }} 
                  />
                  <Bar dataKey="hired" fill="#10b981" name="Hired" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="open" fill="#f59e0b" name="Open" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Skill Heatmap (as horizontal bar chart) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Skills in Candidate Pool</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={skillHeatmap.slice(0, 10)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" className="text-xs" />
                  <YAxis dataKey="skill" type="category" className="text-xs" width={100} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'hsl(var(--card))', 
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }} 
                  />
                  <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Skill Heatmap Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Skills Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {skillHeatmap.map((skill) => {
              const intensity = Math.min(skill.count * 15, 100)
              return (
                <div
                  key={skill.skill}
                  className="p-3 rounded-lg border text-center"
                  style={{
                    backgroundColor: `hsl(var(--primary) / ${intensity / 100 * 0.3})`,
                  }}
                >
                  <p className="font-medium text-sm">{skill.skill}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {skill.count} candidates
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Avg: {skill.avg_score?.toFixed(1)}
                  </p>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
