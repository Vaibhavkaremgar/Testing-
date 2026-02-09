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
import { Search, Bell, Sun, Moon, LogOut, User, Settings, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

export function Header() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState([])
  const [showNotifications, setShowNotifications] = useState(false)
  const isDark = theme === 'dark'

  // Fetch real notifications
  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const [candidates, interviews] = await Promise.all([
          api.getCandidates({ limit: 5 }),
          api.getInterviews({ limit: 3 })
        ])
        
        const notificationList = []
        
        // Recent candidates
        candidates.slice(0, 3).forEach(candidate => {
          const timeDiff = new Date() - new Date(candidate.created_at)
          const hoursAgo = Math.floor(timeDiff / (1000 * 60 * 60))
          const timeText = hoursAgo < 1 ? 'Just now' : hoursAgo < 24 ? `${hoursAgo}h ago` : `${Math.floor(hoursAgo / 24)}d ago`
          
          notificationList.push({
            id: `candidate-${candidate.id}`,
            type: 'candidate',
            message: `New candidate ${candidate.name} applied${candidate.job_title ? ` for ${candidate.job_title}` : ''}`,
            time: timeText,
            unread: hoursAgo < 24,
            data: candidate
          })
        })
        
        // Recent interviews
        interviews.slice(0, 2).forEach(interview => {
          const timeDiff = new Date() - new Date(interview.created_at)
          const hoursAgo = Math.floor(timeDiff / (1000 * 60 * 60))
          const timeText = hoursAgo < 1 ? 'Just now' : hoursAgo < 24 ? `${hoursAgo}h ago` : `${Math.floor(hoursAgo / 24)}d ago`
          
          notificationList.push({
            id: `interview-${interview.id}`,
            type: 'interview',
            message: `Interview ${interview.status === 'completed' ? 'completed' : 'scheduled'} with ${interview.candidate_name}`,
            time: timeText,
            unread: hoursAgo < 12,
            data: interview
          })
        })
        
        setNotifications(notificationList.sort((a, b) => b.unread - a.unread))
      } catch (error) {
        console.error('Failed to fetch notifications:', error)
        // Fallback to mock data
        setNotifications([
          { id: 1, type: 'system', message: 'Welcome to HireFlow!', time: '1 hour ago', unread: true },
          { id: 2, type: 'system', message: 'System maintenance scheduled', time: '2 hours ago', unread: false },
        ])
      }
    }
    
    fetchNotifications()
    // Refresh notifications every 5 minutes
    const interval = setInterval(fetchNotifications, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const unreadCount = notifications.filter(n => n.unread).length

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const markAsRead = (notificationId) => {
    setNotifications(prev => 
      prev.map(n => n.id === notificationId ? { ...n, unread: false } : n)
    )
  }

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, unread: false })))
  }

  const handleNotificationClick = (notification) => {
    markAsRead(notification.id)
    
    // Navigate based on notification type
    if (notification.type === 'candidate') {
      navigate('/resumes')
    } else if (notification.type === 'interview') {
      navigate('/interviews')
    }
    
    setShowNotifications(false)
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
        backgroundColor: isDark ? '' : '#ffffff', 
        boxShadow: isDark ? '' : '0 1px 2px 0 rgb(0 0 0 / 0.05)' 
      }}
    >
      {/* Search */}
      <div className="flex items-center gap-4 flex-1 max-w-md">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search candidates, jobs..."
            className="pl-10"
          />
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
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
            <DropdownMenuItem onClick={() => navigate('/settings')}>
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
