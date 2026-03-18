import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Building2, Users, Briefcase, UserCheck, Video, Wallet } from 'lucide-react'

export default function SuperAdminDashboard() {
  const [agencies, setAgencies] = useState([])
  const [selectedAgency, setSelectedAgency] = useState('')
  const [stats, setStats] = useState({ jobs: 0, candidates: 0, interviews: 0, clients: 0, users: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getAgencies().then(setAgencies).catch(console.error)
  }, [])

  useEffect(() => {
    fetchStats()
  }, [selectedAgency])

  const fetchStats = async () => {
    setLoading(true)
    try {
      const params = selectedAgency ? { agency_id: selectedAgency } : {}
      const [jobs, candidates, interviews, clients] = await Promise.all([
        api.getJobsCount(params).catch(() => ({ count: 0 })),
        api.getCandidatesCount(params).catch(() => ({ count: 0 })),
        api.getInterviewsCount(params).catch(() => ({ count: 0 })),
        api.getClientsCount().catch(() => ({ count: 0 })),
      ])
      setStats({
        jobs: jobs.count,
        candidates: candidates.count,
        interviews: interviews.count,
        clients: clients.count,
      })
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const statCards = [
    { label: 'Total Agencies', value: agencies.length, icon: Building2, color: 'text-purple-500' },
    { label: 'Jobs', value: stats.jobs, icon: Briefcase, color: 'text-blue-500' },
    { label: 'Candidates', value: stats.candidates, icon: UserCheck, color: 'text-green-500' },
    { label: 'Interviews', value: stats.interviews, icon: Video, color: 'text-orange-500' },
    { label: 'Clients', value: stats.clients, icon: Users, color: 'text-pink-500' },
  ]

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Super Admin Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">Overview across all agencies</p>
        </div>

        {/* Agency Filter */}
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-muted-foreground" />
          <select
            className="border rounded-lg px-3 py-2 text-sm bg-background"
            value={selectedAgency}
            onChange={(e) => setSelectedAgency(e.target.value)}
          >
            <option value="">All Agencies</option>
            {agencies.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {statCards.map((card) => (
          <Card key={card.label}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{card.label}</p>
                  <p className="text-2xl font-bold mt-1">
                    {loading ? '...' : card.value}
                  </p>
                </div>
                <card.icon className={`h-8 w-8 ${card.color}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Agencies Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {selectedAgency
              ? `Agency: ${agencies.find(a => String(a.id) === String(selectedAgency))?.name}`
              : 'All Agencies'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground">
                <th className="text-left py-2 font-medium">Agency Name</th>
                <th className="text-left py-2 font-medium">Slug</th>
                <th className="text-left py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {agencies
                .filter(a => !selectedAgency || String(a.id) === String(selectedAgency))
                .map((agency) => (
                  <tr key={agency.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="py-2 font-medium">{agency.name}</td>
                    <td className="py-2 text-muted-foreground">{agency.slug}</td>
                    <td className="py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${agency.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                        {agency.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                  </tr>
                ))}
              {agencies.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-6 text-center text-muted-foreground">No agencies found</td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
