import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Mail, Send, Search, Filter, X } from 'lucide-react'
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
        filtered = communications.filter(c => c.type === 'Shortlisted')
        break
      case 'resume_rejected':
        filtered = communications.filter(c => c.type === 'Resume Rejected')
        break
      case 'interview':
        filtered = communications.filter(c => c.type === 'Interview Invitation')
        break
      case 'selection':
        filtered = communications.filter(c => c.type === 'Selection')
        break
      case 'interview_rejected':
        filtered = communications.filter(c => c.type === 'Interview Rejected')
        break
      case 'offer':
        filtered = communications.filter(c => c.type === 'Offer Letter')
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
  }, [])

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

  // Calculate stats from real data
  const stats = [
    { 
      label: 'Shortlisted Emails', 
      value: communications.filter(c => c.type === 'Shortlisted').length, 
      icon: Mail, 
      color: 'text-blue-600',
      type: 'shortlisted'
    },
    { 
      label: 'Resume Rejected', 
      value: communications.filter(c => c.type === 'Resume Rejected').length, 
      icon: Mail, 
      color: 'text-red-600',
      type: 'resume_rejected'
    },
    { 
      label: 'Interview Invites', 
      value: communications.filter(c => c.type === 'Interview Invitation').length, 
      icon: Send, 
      color: 'text-purple-600',
      type: 'interview'
    },
    { 
      label: 'Selection Emails', 
      value: communications.filter(c => c.type === 'Selection').length, 
      icon: Mail, 
      color: 'text-green-600',
      type: 'selection'
    },
    { 
      label: 'Interview Rejected', 
      value: communications.filter(c => c.type === 'Interview Rejected').length, 
      icon: Mail, 
      color: 'text-orange-600',
      type: 'interview_rejected'
    },
    { 
      label: 'Offer Letters', 
      value: communications.filter(c => c.type === 'Offer Letter').length, 
      icon: Send, 
      color: 'text-teal-600',
      type: 'offer'
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

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-6">
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
