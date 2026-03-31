import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

export default function Communications() {
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const [searchTerm, setSearchTerm] = useState('')
  const [typeFilter, setTypeFilter] = useState([])
  const [statusFilter, setStatusFilter] = useState([])
  const [communications, setCommunications] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedStat, setSelectedStat] = useState(null)
  const [filteredEmails, setFilteredEmails] = useState([])
  const [selectedEmail, setSelectedEmail] = useState(null)
  const [visibleCount, setVisibleCount] = useState(20)
  const [deleteCommunicationModal, setDeleteCommunicationModal] = useState({ open: false, communicationId: null })
  const SHOW_MORE_STEP = 20

  useEffect(() => { setVisibleCount(20) }, [searchTerm, typeFilter, statusFilter])

  const handleStatClick = (statType) => {
    let filtered = []
    switch(statType) {
      case 'shortlisted':
        filtered = communications.filter(c => 
          c.email_type === 'Shortlisted' || 
          c.email_type === 'Slot Selection Email' || 
          c.email_type === 'Interview Invitation'
        )
        break
      case 'rejected':
        filtered = communications.filter(c => 
          c.email_type === 'Rejection Email' || 
          c.email_type === 'Interview Rejected'
        )
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
  }, [selectedClient])

  const handleDelete = async (id) => {
    setDeleteCommunicationModal({ open: true, communicationId: id })
  }

  const handleConfirmDelete = async () => {
    const communicationId = deleteCommunicationModal.communicationId
    if (!communicationId) return

    try {
      await api.deleteEmailCommunication(communicationId)
      setCommunications(prev => prev.filter(c => c.id !== communicationId))
      setFilteredEmails(prev => prev.filter(c => c.id !== communicationId))
      if (selectedEmail?.id === communicationId) {
        setSelectedEmail(null)
      }
      setDeleteCommunicationModal({ open: false, communicationId: null })
      alert('Email record deleted successfully')
    } catch (error) {
      console.error('Failed to delete email:', error)
      alert('Failed to delete email record')
    }
  }

  const fetchCommunications = async () => {
    try {
      const params = {}
      if (selectedClient) params.client = selectedClient
      const data = await api.getCommunications(params)
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
      value: communications.filter(c => 
        c.email_type === 'Shortlisted' || 
        c.email_type === 'Slot Selection Email' || 
        c.email_type === 'Interview Invitation'
      ).length, 
      icon: Mail, 
      color: 'text-blue-600',
      type: 'shortlisted'
    },
    { 
      label: 'Rejected Emails', 
      value: communications.filter(c => 
        c.email_type === 'Rejection Email' || 
        c.email_type === 'Interview Rejected'
      ).length, 
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
      (comm.candidate_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (comm.candidate_email || '').toLowerCase().includes(searchTerm.toLowerCase())
    
    const matchesType = typeFilter.length === 0 || typeFilter.includes(comm.email_type)
    const matchesStatus = statusFilter.length === 0 || statusFilter.includes((comm.status || '').charAt(0).toUpperCase() + (comm.status || '').slice(1))
    
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
    const normalizedStatus = (status || '').charAt(0).toUpperCase() + (status || '').slice(1)
    const variants = {
      Sent: 'default',
      Pending: 'secondary',
      Failed: 'destructive'
    }
    return <Badge variant={variants[normalizedStatus]}>{normalizedStatus}</Badge>
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
                </tr>
              </thead>
              <tbody>
                {filteredCommunications.slice(0, visibleCount).map((comm) => (
                  <tr key={comm.id} className="border-b hover:bg-muted/50 cursor-pointer" onClick={() => setSelectedEmail(comm)}>
                    <td className="p-3 text-sm">{comm.candidate_name}</td>
                    <td className="p-3 text-sm text-muted-foreground">{comm.candidate_email}</td>
                    <td className="p-3 text-sm">{comm.email_type}</td>
                    <td className="p-3 text-sm">{getStatusBadge(comm.status)}</td>
                    <td className="p-3 text-sm">{comm.sent_at ? new Date(comm.sent_at).toLocaleString() : new Date(comm.created_at).toLocaleString()}</td>
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
          {visibleCount < filteredCommunications.length && (
            <div className="flex justify-center p-4 border-t">
              <Button variant="outline" onClick={() => setVisibleCount(v => v + SHOW_MORE_STEP)}>
                Show More ({filteredCommunications.length - visibleCount} remaining)
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Email Details Modal */}
      {selectedEmail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedEmail(null)}>
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Email Details</h2>
              <Button variant="ghost" size="icon" onClick={() => setSelectedEmail(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Candidate Name</p>
                  <p className="font-medium">{selectedEmail.candidate_name}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Email</p>
                  <p>{selectedEmail.candidate_email}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Type</p>
                  <p>{selectedEmail.email_type}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <div>{getStatusBadge(selectedEmail.status)}</div>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Date</p>
                  <p>{selectedEmail.sent_at ? new Date(selectedEmail.sent_at).toLocaleString() : new Date(selectedEmail.created_at).toLocaleString()}</p>
                </div>
              </div>
              
              {selectedEmail.body && (
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Email Message</p>
                  <div className="bg-muted p-4 rounded-lg whitespace-pre-wrap text-sm">
                    {selectedEmail.body}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

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
                        <tr key={comm.id} className="border-b hover:bg-muted/50 cursor-pointer" onClick={() => setSelectedEmail(comm)}>
                          <td className="p-3 text-sm">{comm.candidate_name}</td>
                          <td className="p-3 text-sm text-muted-foreground">{comm.candidate_email}</td>
                          <td className="p-3 text-sm">{comm.email_type}</td>
                          <td className="p-3 text-sm">{getStatusBadge(comm.status)}</td>
                          <td className="p-3 text-sm">{comm.sent_at ? new Date(comm.sent_at).toLocaleString() : new Date(comm.created_at).toLocaleString()}</td>
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

      <Dialog
        open={deleteCommunicationModal.open}
        onOpenChange={(open) => setDeleteCommunicationModal({ open, communicationId: open ? deleteCommunicationModal.communicationId : null })}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Communication</DialogTitle>
            <DialogDescription>Are you sure to delete</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteCommunicationModal({ open: false, communicationId: null })}
            >
              Cancel
            </Button>
            <Button
              className="bg-red-600 text-white hover:bg-red-700"
              onClick={handleConfirmDelete}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
