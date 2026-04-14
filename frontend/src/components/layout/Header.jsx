import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Search, Bell, Sun, Moon, LogOut, User, Settings, X, ChevronDown } from 'lucide-react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'

const CLIENT_FILTER_STORAGE_KEY = 'selectedClientFilter'
const JOB_FILTER_STORAGE_KEY = 'selectedJobFilter'

export function Header() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [notifications, setNotifications] = useState([])
  const [showNotifications, setShowNotifications] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showSearchResults, setShowSearchResults] = useState(false)
  const [shouldLoadFilterOptions, setShouldLoadFilterOptions] = useState(() => Boolean(
    searchParams.get('client') ||
    searchParams.get('job_id') ||
    localStorage.getItem(CLIENT_FILTER_STORAGE_KEY) ||
    localStorage.getItem(JOB_FILTER_STORAGE_KEY),
  ))
  const [selectedClient, setSelectedClient] = useState(() => (
    searchParams.get('client') ||
    localStorage.getItem(CLIENT_FILTER_STORAGE_KEY) ||
    ''
  ))
  const isDark = theme === 'dark'
  const debouncedSearchQuery = useDebouncedValue(searchQuery, 300)

  const filterOptionsQuery = useQuery({
    queryKey: ['header-filter-options'],
    enabled: shouldLoadFilterOptions,
    queryFn: async () => {
      const jobsData = await api.getJobs({ limit: 100, offset: 0 })
      const uniqueClients = [...new Set((jobsData || []).map((job) => job.company_name).filter(Boolean))]
      return {
        jobs: jobsData || [],
        clients: uniqueClients.sort(),
      }
    },
  })

  const notificationsQuery = useQuery({
    queryKey: ['header-notifications'],
    enabled: showNotifications,
    queryFn: async () => {
      const [candidates, interviews] = await Promise.all([
        api.getCandidates({ limit: 5, offset: 0 }),
        api.getInterviews({ limit: 3, offset: 0 }),
      ])

      const readNotifications = JSON.parse(localStorage.getItem('readNotifications') || '[]')
      const notificationList = []

      candidates.slice(0, 3).forEach((candidate) => {
        const timeDiff = new Date() - new Date(candidate.created_at)
        const hoursAgo = Math.floor(timeDiff / (1000 * 60 * 60))
        const timeText = hoursAgo < 1 ? 'Just now' : hoursAgo < 24 ? `${hoursAgo}h ago` : `${Math.floor(hoursAgo / 24)}d ago`
        const notifId = `candidate-${candidate.id}`

        notificationList.push({
          id: notifId,
          type: 'candidate',
          message: `New candidate ${candidate.name} applied${candidate.job_title ? ` for ${candidate.job_title}` : ''}`,
          time: timeText,
          unread: hoursAgo < 24 && !readNotifications.includes(notifId),
          data: candidate,
        })
      })

      interviews.slice(0, 2).forEach((interview) => {
        const timeDiff = new Date() - new Date(interview.created_at)
        const hoursAgo = Math.floor(timeDiff / (1000 * 60 * 60))
        const timeText = hoursAgo < 1 ? 'Just now' : hoursAgo < 24 ? `${hoursAgo}h ago` : `${Math.floor(hoursAgo / 24)}d ago`
        const notifId = `interview-${interview.id}`

        notificationList.push({
          id: notifId,
          type: 'interview',
          message: `Interview ${interview.status === 'completed' ? 'completed' : 'scheduled'} with ${interview.candidate_name}`,
          time: timeText,
          unread: hoursAgo < 12 && !readNotifications.includes(notifId),
          data: interview,
        })
      })

      return notificationList.sort((a, b) => b.unread - a.unread)
    },
    refetchInterval: showNotifications ? 5 * 60 * 1000 : false,
  })

  const globalSearchQuery = useQuery({
    queryKey: ['global-search', debouncedSearchQuery],
    enabled: debouncedSearchQuery.trim().length >= 2,
    queryFn: async () => {
      const [candidates, jobs, interviews] = await Promise.all([
        api.getCandidates({ search: debouncedSearchQuery, limit: 5, offset: 0 }),
        api.getJobs({ search: debouncedSearchQuery, limit: 5, offset: 0 }),
        api.getInterviews({ limit: 20, offset: 0 }),
      ])

      return {
        candidates,
        jobs,
        interviews: interviews
          .filter((interview) => interview.candidate_name?.toLowerCase().includes(debouncedSearchQuery.toLowerCase()))
          .slice(0, 5),
      }
    },
  })

  const clients = filterOptionsQuery.data?.clients || []
  const searchResults = globalSearchQuery.data || { candidates: [], jobs: [], interviews: [] }
  const searching = globalSearchQuery.isFetching

  useEffect(() => {
    const urlClient = searchParams.get('client') || ''
    const urlJobId = searchParams.get('job_id') || ''
    const storedClient = localStorage.getItem(CLIENT_FILTER_STORAGE_KEY) || ''
    const storedJobId = localStorage.getItem(JOB_FILTER_STORAGE_KEY) || ''
    const nextClient = urlClient || storedClient
    const nextJobId = urlJobId || storedJobId
    const nextParams = new URLSearchParams(searchParams)
    let shouldReplace = false

    setSelectedClient(nextClient)
    if (nextClient) {
      localStorage.setItem(CLIENT_FILTER_STORAGE_KEY, nextClient)
      if (urlClient !== nextClient) {
        nextParams.set('client', nextClient)
        shouldReplace = true
      }
    } else {
      localStorage.removeItem(CLIENT_FILTER_STORAGE_KEY)
      if (urlClient) {
        nextParams.delete('client')
        shouldReplace = true
      }
    }

    if (nextJobId) {
      localStorage.setItem(JOB_FILTER_STORAGE_KEY, nextJobId)
      if (urlJobId !== nextJobId) {
        nextParams.set('job_id', nextJobId)
        shouldReplace = true
      }
    } else {
      localStorage.removeItem(JOB_FILTER_STORAGE_KEY)
      if (urlJobId) {
        nextParams.delete('job_id')
        shouldReplace = true
      }
    }

    if (shouldReplace) {
      setSearchParams(nextParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (notificationsQuery.data) {
      setNotifications(notificationsQuery.data)
    }
  }, [notificationsQuery.data])

  useEffect(() => {
    if (debouncedSearchQuery.trim().length < 2) {
      setShowSearchResults(false)
      return
    }

    if (globalSearchQuery.data) {
      setShowSearchResults(true)
    }
  }, [debouncedSearchQuery, globalSearchQuery.data])

  const buildGlobalAwarePath = (pathname) => {
    const activeClient = searchParams.get('client') || localStorage.getItem(CLIENT_FILTER_STORAGE_KEY) || ''
    const activeJobId = searchParams.get('job_id') || localStorage.getItem(JOB_FILTER_STORAGE_KEY) || ''
    const nextParams = new URLSearchParams()
    if (activeClient) nextParams.set('client', activeClient)
    if (activeJobId) nextParams.set('job_id', activeJobId)
    const query = nextParams.toString()
    return query ? `${pathname}?${query}` : pathname
  }

  // Handle client selection
  const handleClientChange = (client) => {
    setSelectedClient(client)
    setSelectedJobId('')
    const nextParams = new URLSearchParams(searchParams)
    if (client) {
      localStorage.setItem(CLIENT_FILTER_STORAGE_KEY, client)
      nextParams.set('client', client)
    } else {
      localStorage.removeItem(CLIENT_FILTER_STORAGE_KEY)
      nextParams.delete('client')
    }
    localStorage.removeItem(JOB_FILTER_STORAGE_KEY)
    nextParams.delete('job_id')
    setSearchParams(nextParams, { replace: location.pathname !== '/login' })
  }

  const unreadCount = notifications.filter(n => n.unread).length

  const handleLogout = () => {
    logout()
    localStorage.removeItem(CLIENT_FILTER_STORAGE_KEY)
    localStorage.removeItem(JOB_FILTER_STORAGE_KEY)
    navigate('/login')
  }

  const markAsRead = (notificationId) => {
    setNotifications(prev => 
      prev.map(n => n.id === notificationId ? { ...n, unread: false } : n)
    )
    const readNotifications = JSON.parse(localStorage.getItem('readNotifications') || '[]')
    if (!readNotifications.includes(notificationId)) {
      localStorage.setItem('readNotifications', JSON.stringify([...readNotifications, notificationId]))
    }
  }

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, unread: false })))
    const allIds = notifications.map(n => n.id)
    localStorage.setItem('readNotifications', JSON.stringify(allIds))
  }

  const handleNotificationClick = (notification) => {
    markAsRead(notification.id)
    
    // Navigate based on notification type
    if (notification.type === 'candidate') {
      navigate(buildGlobalAwarePath('/resumes'))
    } else if (notification.type === 'interview') {
      navigate(buildGlobalAwarePath('/interviews'))
    }
    
    setShowNotifications(false)
  }

  const handleOpenFilterOptions = () => {
    if (!shouldLoadFilterOptions) {
      setShouldLoadFilterOptions(true)
    }
  }

  const getInitials = (name) => {
    return name
      ?.split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) || 'U'
  }

  return (
    <header 
      className="flex h-16 items-center justify-between border-b px-6" 
      style={{ 
        backgroundColor: isDark ? 'rgb(15, 23, 42)' : 'rgb(255, 255, 255)', 
        boxShadow: isDark ? '0 1px 3px 0 rgb(0 0 0 / 0.3)' : '0 1px 3px 0 rgb(0 0 0 / 0.1)' 
      }}
    >
      {/* Search */}
      <div className="flex items-center gap-4 flex-1 max-w-md relative">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search candidates, jobs, interviews..."
            className="pl-10"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => searchQuery && setShowSearchResults(true)}
          />
          {searchQuery && (
            <Button
              variant="ghost"
              size="sm"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
              onClick={() => {
                setSearchQuery('')
                setShowSearchResults(false)
              }}
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>

        {/* Search Results Dropdown */}
        {showSearchResults && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-card border rounded-lg shadow-lg max-h-96 overflow-y-auto z-50">
            {searching ? (
              <div className="p-4 text-center text-muted-foreground">Searching...</div>
            ) : (
              <div className="p-2">
                {/* Candidates */}
                {searchResults.candidates.length > 0 && (
                  <div className="mb-2">
                    <p className="text-xs font-semibold text-muted-foreground px-2 py-1">CANDIDATES</p>
                    {searchResults.candidates.map(candidate => (
                      <div
                        key={candidate.id}
                        className="px-3 py-2 hover:bg-accent rounded cursor-pointer"
                        onClick={() => {
                          navigate(buildGlobalAwarePath('/resumes'))
                          setShowSearchResults(false)
                          setSearchQuery('')
                        }}
                      >
                        <p className="text-sm font-medium">{candidate.name}</p>
                        <p className="text-xs text-muted-foreground">{candidate.email} • {candidate.job_title || 'No job'}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Jobs */}
                {searchResults.jobs.length > 0 && (
                  <div className="mb-2">
                    <p className="text-xs font-semibold text-muted-foreground px-2 py-1">JOBS</p>
                    {searchResults.jobs.map(job => (
                      <div
                        key={job.id}
                        className="px-3 py-2 hover:bg-accent rounded cursor-pointer"
                        onClick={() => {
                          navigate(buildGlobalAwarePath('/jobs'))
                          setShowSearchResults(false)
                          setSearchQuery('')
                        }}
                      >
                        <p className="text-sm font-medium">{job.title}</p>
                        <p className="text-xs text-muted-foreground">{job.company_name || 'Company'} • {job.location || 'Location'}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Interviews */}
                {searchResults.interviews.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground px-2 py-1">INTERVIEWS</p>
                    {searchResults.interviews.map(interview => (
                      <div
                        key={interview.id}
                        className="px-3 py-2 hover:bg-accent rounded cursor-pointer"
                        onClick={() => {
                          navigate(buildGlobalAwarePath('/interviews'))
                          setShowSearchResults(false)
                          setSearchQuery('')
                        }}
                      >
                        <p className="text-sm font-medium">{interview.candidate_name}</p>
                        <p className="text-xs text-muted-foreground">{interview.interview_type} • {interview.status}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* No results */}
                {searchResults.candidates.length === 0 && 
                 searchResults.jobs.length === 0 && 
                 searchResults.interviews.length === 0 && (
                  <div className="p-4 text-center text-muted-foreground">
                    No results found for "{searchQuery}"
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Client Filter */}
          <div className="relative">
            <select
              className="h-9 rounded-md border border-input bg-background pl-3 pr-10 text-sm appearance-none"
              value={selectedClient}
              onChange={(e) => handleClientChange(e.target.value)}
              onFocus={handleOpenFilterOptions}
              onPointerDown={handleOpenFilterOptions}
            >
              <option value="">All Clients</option>
              {clients.map((client) => (
                <option key={client} value={client}>
                  {client}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>

        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          {theme === 'dark' ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        {/* Notifications */}
        <DropdownMenu open={showNotifications} onOpenChange={setShowNotifications}>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute -right-1 -top-1 h-5 w-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-80" align="end">
            <div className="flex items-center justify-between p-3">
              <DropdownMenuLabel className="p-0">Notifications</DropdownMenuLabel>
              {unreadCount > 0 && (
                <Button variant="ghost" size="sm" onClick={markAllAsRead} className="text-xs h-6">
                  Mark all read
                </Button>
              )}
            </div>
            <DropdownMenuSeparator />
            <div className="max-h-80 overflow-y-auto">
              {notifications.length > 0 ? (
                notifications.map((notification) => (
                  <DropdownMenuItem 
                    key={notification.id} 
                    className="flex flex-col items-start p-3 cursor-pointer hover:bg-accent"
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <div className="flex items-start justify-between w-full">
                      <p className={`text-sm ${notification.unread ? 'font-medium' : 'text-muted-foreground'}`}>
                        {notification.message}
                      </p>
                      <div className="flex items-center gap-2 ml-2">
                        {notification.unread && (
                          <span className="h-2 w-2 rounded-full bg-blue-500" />
                        )}
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-4 w-4 p-0 hover:bg-destructive hover:text-white"
                          onClick={(e) => {
                            e.stopPropagation()
                            setNotifications(prev => prev.filter(n => n.id !== notification.id))
                          }}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{notification.time}</p>
                  </DropdownMenuItem>
                ))
              ) : (
                <DropdownMenuItem disabled className="justify-center">
                  <p className="text-sm text-muted-foreground">No notifications</p>
                </DropdownMenuItem>
              )}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative h-10 w-10 rounded-full">
              <Avatar className="h-9 w-9">
                <AvatarFallback className="bg-primary text-primary-foreground">
                  {getInitials(user?.full_name)}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56" align="end" forceMount>
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none">{user?.full_name}</p>
                <p className="text-xs leading-none text-muted-foreground">
                  {user?.email}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate('/profile')}>
              <User className="mr-2 h-4 w-4" />
              <span>Profile</span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate('/settings')}>
              <Settings className="mr-2 h-4 w-4" />
              <span>Settings</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              <span>Log out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
