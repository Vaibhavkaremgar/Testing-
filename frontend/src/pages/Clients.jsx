import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { Pagination } from '@/components/ui/pagination'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Plus, Building2, TrendingUp, TrendingDown, Users, Edit, Trash2, X } from 'lucide-react'

export default function Clients() {
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const { user } = useAuth()
  const [clients, setClients] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingClient, setEditingClient] = useState(null)
  const [selectedStat, setSelectedStat] = useState(null)
  const [filteredClients, setFilteredClients] = useState([])
  const [currentPage, setCurrentPage] = useState(1)
  const [totalClients, setTotalClients] = useState(0)
  const ITEMS_PER_PAGE = 10
  const [formData, setFormData] = useState({
    company_name: '', industry: '', contact_person: '', contact_email: '', contact_phone: '',
    total_positions: 0, positions_filled: 0, positions_open: 0
  })

  useEffect(() => {
    fetchData()
  }, [selectedClient, currentPage])

  // Reset to page 1 when client filter changes
  useEffect(() => {
    setCurrentPage(1)
  }, [selectedClient])

  const handleStatClick = (statType) => {
    let filtered = []
    switch(statType) {
      case 'total':
        filtered = clients
        break
      case 'active':
        filtered = clients.filter(c => c.is_active)
        break
      case 'total_positions':
        filtered = clients.filter(c => c.total_positions > 0)
        break
      case 'open':
        filtered = clients.filter(c => c.positions_open > 0)
        break
      case 'filled':
        filtered = clients.filter(c => c.positions_filled > 0)
        break
      default:
        filtered = clients
    }
    setFilteredClients(filtered)
    setSelectedStat(statType)
  }

  const closeStatModal = () => {
    setSelectedStat(null)
    setFilteredClients([])
  }

  const fetchData = async () => {
    try {
      // Get stats from backend (filtered by client if selected)
      const statsData = await api.getClientStats()
      
      // Get unique clients from jobs (filtered by client if selected) with pagination
      const jobsParams = selectedClient ? { client: selectedClient } : {}
      const jobs = await api.getJobs(jobsParams)
      const clientMap = new Map()
      
      jobs.forEach(job => {
        const companyName = job.company_name
        if (!companyName) return
        
        if (!clientMap.has(companyName)) {
          clientMap.set(companyName, {
            id: companyName,
            name: companyName,
            industry: job.department || 'N/A',
            total_positions: 0,
            positions_filled: 0,
            positions_open: 0,
            is_active: job.is_active,
            acceptance_rate: 0,
            avg_time_to_hire: 0
          })
        }
        
        const client = clientMap.get(companyName)
        if (job.is_active) {
          client.total_positions += job.vacancies || 0
        }
      })
      
      // Get candidates to calculate filled positions (filtered by client if selected)
      const candidatesParams = selectedClient ? { client: selectedClient } : {}
      const candidates = await api.getCandidates(candidatesParams)
      candidates.forEach(candidate => {
        if (candidate.stage === 'SELECTED' && candidate.job_id) {
          const job = jobs.find(j => j.id === candidate.job_id)
          if (job && job.company_name) {
            const client = clientMap.get(job.company_name)
            if (client) {
              client.positions_filled++
            }
          }
        }
      })
      
      // Calculate open positions
      clientMap.forEach(client => {
        client.positions_open = client.total_positions - client.positions_filled
      })
      
      const clientsList = Array.from(clientMap.values())
      
      // Paginate clients list
      const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
      const endIndex = startIndex + ITEMS_PER_PAGE
      const paginatedClients = clientsList.slice(startIndex, endIndex)
      
      setClients(paginatedClients)
      setTotalClients(clientsList.length)
      
      // Calculate filtered stats
      const filteredStats = {
        total_clients: clientsList.length,
        active_clients: clientsList.filter(c => c.is_active).length,
        total_positions: clientsList.reduce((sum, c) => sum + c.total_positions, 0),
        open_positions: clientsList.reduce((sum, c) => sum + c.positions_open, 0),
        filled_positions: clientsList.reduce((sum, c) => sum + c.positions_filled, 0)
      }
      setStats(filteredStats)
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingClient) {
        await api.updateClient(editingClient.id, formData)
      } else {
        await api.createClient(formData)
      }
      setDialogOpen(false)
      setEditingClient(null)
      setFormData({
        company_name: '', industry: '', contact_person: '', contact_email: '', contact_phone: '',
        total_positions: 0, positions_filled: 0, positions_open: 0
      })
      await fetchData()
    } catch (error) {
      console.error('Failed to save client:', error)
    }
  }

  const handleEdit = (client) => {
    setEditingClient(client)
    setFormData({
      company_name: client.company_name || client.name,
      industry: client.industry || '',
      contact_person: client.contact_person || '',
      contact_email: client.contact_email || '',
      contact_phone: client.contact_phone || '',
      total_positions: client.total_positions || 0,
      positions_filled: client.positions_filled || 0,
      positions_open: client.positions_open || 0
    })
    setDialogOpen(true)
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this client?')) {
      return
    }
    try {
      await api.deleteClient(id)
      await fetchData()
    } catch (error) {
      console.error('Failed to delete client:', error)
      alert('Failed to delete client: ' + error.message)
    }
  }



  const topPerformers = clients
    .filter(c => c.acceptance_rate > 0)
    .sort((a, b) => b.acceptance_rate - a.acceptance_rate)
    .slice(0, 5)

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
          <h1 className="text-2xl font-bold">Clients</h1>
          <p className="text-muted-foreground">Manage client relationships and hiring progress</p>
        </div>
        {user?.role === 'admin' && (
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={() => {
                setEditingClient(null)
                setFormData({
                  company_name: '', industry: '', contact_person: '', contact_email: '', contact_phone: '',
                  total_positions: 0, positions_filled: 0, positions_open: 0
                })
              }}>
                <Plus className="h-4 w-4 mr-2" />
                Add Client
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>{editingClient ? 'Edit Client' : 'Add New Client'}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4 mt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Company Name *</label>
                    <Input
                      value={formData.company_name}
                      onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Industry</label>
                    <Input
                      value={formData.industry}
                      onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Contact Person</label>
                    <Input
                      value={formData.contact_person}
                      onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Contact Email</label>
                    <Input
                      type="email"
                      value={formData.contact_email}
                      onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Contact Phone</label>
                    <Input
                      value={formData.contact_phone}
                      onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => {
                    setDialogOpen(false)
                    setFormData({
                      company_name: '', industry: '', contact_person: '', contact_email: '', contact_phone: '',
                      total_positions: 0, positions_filled: 0, positions_open: 0
                    })
                  }}>
                    Cancel
                  </Button>
                  <Button type="submit">
                    {editingClient ? 'Update' : 'Create'} Client
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {stats && (
        <div className="grid gap-4 md:grid-cols-5">
          <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => handleStatClick('total')}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Clients</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_clients}</div>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => handleStatClick('active')}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Active Clients</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.active_clients}</div>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => handleStatClick('total_positions')}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Positions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_positions}</div>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => handleStatClick('open')}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Open Positions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{stats.open_positions}</div>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => handleStatClick('filled')}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Filled Positions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{stats.filled_positions}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-1">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Performing Clients</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {topPerformers.map((client) => (
                <div key={client.id} className="flex items-center justify-between text-sm">
                  <span className="truncate">{client.name}</span>
                  <span className="text-green-600 font-medium">{client.acceptance_rate}%</span>
                </div>
              ))}
              {topPerformers.length === 0 && <p className="text-sm text-muted-foreground">No data available</p>}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Client Hiring Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4 font-medium">Client</th>
                  <th className="text-left py-3 px-4 font-medium">Industry</th>
                  <th className="text-center py-3 px-4 font-medium">Total</th>
                  <th className="text-center py-3 px-4 font-medium">Filled</th>
                  <th className="text-center py-3 px-4 font-medium">Open</th>
                  <th className="text-left py-3 px-4 font-medium">Progress</th>
                  <th className="text-center py-3 px-4 font-medium">Avg Time</th>
                  <th className="text-center py-3 px-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => {
                  const fillRate = client.total_positions > 0 ? (client.positions_filled / client.total_positions) * 100 : 0
                  return (
                    <tr key={client.id} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-4 font-medium">{client.company_name || client.name}</td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">{client.industry || '-'}</td>
                      <td className="py-3 px-4 text-center">{client.total_positions}</td>
                      <td className="py-3 px-4 text-center text-red-600">{client.positions_filled}</td>
                      <td className="py-3 px-4 text-center text-green-600">{client.positions_open}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <Progress value={fillRate} className="h-2 flex-1" />
                          <span className="text-xs text-muted-foreground w-10">{fillRate.toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-center text-sm">{client.avg_time_to_hire || 0}d</td>
                      <td className="py-3 px-4">
                        <div className="flex justify-center gap-1">
                          <Button variant="ghost" size="icon" onClick={() => handleDelete(client.id)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {clients.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No clients found. Add your first client to get started.
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Pagination */}
      <Pagination
        currentPage={currentPage}
        totalPages={Math.ceil(totalClients / ITEMS_PER_PAGE)}
        totalItems={totalClients}
        itemsPerPage={ITEMS_PER_PAGE}
        onPageChange={setCurrentPage}
      />

      {/* Modal for Stat Details */}
      {selectedStat && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={closeStatModal}>
          <div className="bg-card rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Client Details</h2>
              <Button variant="ghost" size="icon" onClick={closeStatModal}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <p className="text-muted-foreground">Total: {filteredClients.length} clients</p>
              
              {filteredClients.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left p-3 font-medium">Client Name</th>
                        <th className="text-left p-3 font-medium">Industry</th>
                        <th className="text-center p-3 font-medium">Total Positions</th>
                        <th className="text-center p-3 font-medium">Filled</th>
                        <th className="text-center p-3 font-medium">Open</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredClients.map((client) => (
                        <tr key={client.id} className="border-b hover:bg-muted/50">
                          <td className="p-3 font-medium">{client.company_name || client.name}</td>
                          <td className="p-3 text-sm text-muted-foreground">{client.industry || '-'}</td>
                          <td className="p-3 text-center">{client.total_positions}</td>
                          <td className="p-3 text-center text-red-600">{client.positions_filled}</td>
                          <td className="p-3 text-center text-green-600">{client.positions_open}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No clients found for this category
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
