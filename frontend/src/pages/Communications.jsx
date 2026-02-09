import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Mail, Send, Search, Filter, X, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export default function Communications() {
  const [searchTerm, setSearchTerm] = useState('')
  const [typeFilter, setTypeFilter] = useState([])
  const [statusFilter, setStatusFilter] = useState([])
  const [communications, setCommunications] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedStat, setSelectedStat] = useState(null)
  const [filteredEmails, setFilteredEmails] = useState([])

  const handleStatClick = (statType) => {
    let filtered = []
    switch(statType) {
      case 'shortlisted':
        filtered = communications.filter(c => c.type === 'Shortlisted' || c.type === 'Slot Selection Email')
        break
      case 'rejected':
        filtered = communications.filter(c => c.type === 'Rejection Email')
        break
      case 'total':
        filtered = communications
        break
      default:
        filtered = communications
    }
    setFilteredEmails(filtered)
    setSelectedStat(statType)
  }

  const closeStatModal = () => {
    setSelectedStat(null)
    setFilteredEmails([])
  }

  useEffect(() => {
    fetchCommunications()
    
    // Auto-refresh every 5 seconds to show new emails
    const interval = setInterval(() => {
      fetchCommunications()
    }, 5000)
    
    return () => clearInterval(interval)
  }, [])

  const handleDelete = async (id) => {
    if (confirm('Are you sure you want to delete this email record?')) {
      try {
        await api.deleteEmailCommunication(id)
        setCommunications(prev => prev.filter(c => c.id !== id))
        alert('Email record deleted successfully')
      } catch (error) {
        console.error('Failed to delete email:', error)
        alert('Failed to delete email record')
      }
    }
  }

  const fetchCommunications = async () => {
    try {
      const data = await api.getCommunications()
      setCommunications(data)
    } catch (error) {
      console.error('Failed to fetch communications:', error)
    } finally {
      setLoading(false)
    }
  }

  // Calculate stats from real data - Total, Shortlisted and Rejected
  const stats = [
    { 
      label: 'Total Emails', 
      value: communications.length, 
      icon: Mail, 
      color: 'text-gray-600',
      type: 'total'
    },
    { 
      label: 'Shortlisted Emails', 
      value: communications.filter(c => c.type === 'Shortlisted' || c.type === 'Slot Selection Email').length, 
      icon: Mail, 
      color: 'text-blue-600',
      type: 'shortlisted'
    },
    { 
      label: 'Rejected Emails', 
      value: communications.filter(c => c.type === 'Rejection Email').length, 
      icon: Mail, 
      color: 'text-red-600',
      type: 'rejected'
    },
  ]

  const emailTypes = ['Shortlisted', 'Resume Rejected', 'Interview Invitation', 'Selection', 'Interview Rejected', 'Offer Letter']
  const statuses = ['Sent', 'Pending', 'Failed']

  // Filter communications
  const filteredCommunications = communications.filter(comm => {
    const matchesSearch = 
      comm.candidate.toLowerCase().includes(searchTerm.toLowerCase()) ||
      comm.email.toLowerCase().includes(searchTerm.toLowerCase())
    
    const matchesType = typeFilter.length === 0 || typeFilter.includes(comm.type)
    const matchesStatus = statusFilter.length === 0 || statusFilter.includes(comm.status)
    
    return matchesSearch && matchesType && matchesStatus
  })

  const toggleTypeFilter = (type) => {
    setTypeFilter(prev => 
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    )
  }

  const toggleStatusFilter = (status) => {
    setStatusFilter(prev => 
      prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]
    )
  }

  const clearFilters = () => {
    setTypeFilter([])
    setStatusFilter([])
    setSearchTerm('')
  }

  const hasActiveFilters = typeFilter.length > 0 || statusFilter.length > 0 || searchTerm

  const getStatusBadge = (status) => {
    const variants = {
      Sent: 'default',
      Pending: 'secondary',
      Failed: 'destructive'
    }
    return <Badge variant={variants[status]}>{status}</Badge>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Communications</h1>
        <p className="text-muted-foreground">Track email communications with candidates</p>
      </div>

      {/* Stats Cards - 3 cards: Total, Shortlisted (includes Slot Selection), Rejected */}
      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.label} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => handleStatClick(stat.type)}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{stat.label}</CardTitle>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Communications Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Email History</CardTitle>
            <div className="flex gap-2">
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8 w-64"
                />
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="icon">
                    <Filter className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel>Filter by Type</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {emailTypes.map((type) => (
                    <DropdownMenuCheckboxItem
                      key={type}
                      checked={typeFilter.includes(type)}
                      onCheckedChange={() => toggleTypeFilter(type)}
                    >
                      {type}
                    </DropdownMenuCheckboxItem>
                  ))}
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel>Filter by Status</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {statuses.map((status) => (
                    <DropdownMenuCheckboxItem
                      key={status}
                      checked={statusFilter.includes(status)}
                      onCheckedChange={() => toggleStatusFilter(status)}
                    >
                      {status}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              {hasActiveFilters && (
                <Button variant="ghost" size="icon" onClick={clearFilters}>
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
          {hasActiveFilters && (
            <div className="flex gap-2 mt-2 flex-wrap">
              {typeFilter.map(type => (
                <Badge key={type} variant="secondary" className="gap-1">
                  {type}
                  <X className="h-3 w-3 cursor-pointer" onClick={() => toggleTypeFilter(type)} />
                </Badge>
              ))}
              {statusFilter.map(status => (
                <Badge key={status} variant="secondary" className="gap-1">
                  {status}
                  <X className="h-3 w-3 cursor-pointer" onClick={() => toggleStatusFilter(status)} />
                </Badge>
              ))}
            </div>
          )}
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="p-3 text-left text-sm font-medium">Candidate</th>
                  <th className="p-3 text-left text-sm font-medium">Email</th>
                  <th className="p-3 text-left text-sm font-medium">Type</th>
                  <th className="p-3 text-left text-sm font-medium">Status</th>
                  <th className="p-3 text-left text-sm font-medium">Date</th>
                  <th className="p-3 text-right text-sm font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCommunications.map((comm) => (
                  <tr key={comm.id} className="border-b hover:bg-muted/50">
                    <td className="p-3 text-sm">{comm.candidate}</td>
                    <td className="p-3 text-sm text-muted-foreground">{comm.email}</td>
                    <td className="p-3 text-sm">{comm.type}</td>
                    <td className="p-3 text-sm">{getStatusBadge(comm.status)}</td>
                    <td className="p-3 text-sm">{comm.date}</td>
                    <td className="p-3 text-right">
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={() => handleDelete(comm.id)}
                        title="Delete email record"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredCommunications.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No communications found
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Modal for Stat Details */}
      {selectedStat && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={closeStatModal}>
          <div className="bg-card rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Email Details</h2>
              <Button variant="ghost" size="icon" onClick={closeStatModal}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <p className="text-muted-foreground">Total: {filteredEmails.length} emails</p>
              
              {filteredEmails.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left p-3 font-medium">Candidate</th>
                        <th className="text-left p-3 font-medium">Email</th>
                        <th className="text-left p-3 font-medium">Type</th>
                        <th className="text-left p-3 font-medium">Status</th>
                        <th className="text-left p-3 font-medium">Date</th>
                        <th className="text-right p-3 font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredEmails.map((comm) => (
                        <tr key={comm.id} className="border-b hover:bg-muted/50">
                          <td className="p-3 text-sm">{comm.candidate}</td>
                          <td className="p-3 text-sm text-muted-foreground">{comm.email}</td>
                          <td className="p-3 text-sm">{comm.type}</td>
                          <td className="p-3 text-sm">{getStatusBadge(comm.status)}</td>
                          <td className="p-3 text-sm">{comm.date}</td>
                          <td className="p-3 text-right">
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              onClick={() => handleDelete(comm.id)}
                              title="Delete email record"
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No emails found for this category
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
