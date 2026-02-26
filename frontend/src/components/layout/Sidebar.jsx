import { NavLink, useSearchParams } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useTheme } from '@/context/ThemeContext'
import {
  LayoutDashboard,
  FileText,
  Users,
  Video,
  BarChart3,
  Settings,
  Briefcase,
  Mail,
  Bot,
  UserCheck,
  Building2,
  MessageSquare
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Jobs', href: '/jobs', icon: Briefcase },
  { name: 'Resumes', href: '/resumes', icon: FileText },
  { name: 'Candidates', href: '/pipeline', icon: Users },
  { name: 'Interviews', href: '/interviews', icon: Video },
  { name: 'Clients', href: '/clients', icon: Building2 },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Communications', href: '/communications', icon: MessageSquare },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Sidebar() {
  const { theme } = useTheme()
  const [searchParams] = useSearchParams()
  const isDark = theme === 'dark'
  
  return (
    <div 
      className="flex h-full w-64 flex-col border-r"
      style={{
        background: isDark ? 'rgb(15, 23, 42)' : 'linear-gradient(to bottom, rgb(241, 245, 249), rgb(248, 250, 252))'
      }}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-6 border-b" style={{ backgroundColor: isDark ? 'rgb(30, 41, 59)' : 'rgb(255, 255, 255)' }}>
        <div>
          <span className="text-lg font-bold">PONTIS</span>
          <p className="text-xs text-muted-foreground">Recruitment System</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => {
          const href = searchParams.toString() ? `${item.href}?${searchParams.toString()}` : item.href
          return (
          <NavLink
            key={item.name}
            to={href}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.name}
          </NavLink>
        )})}
      </nav>

      {/* Footer */}
      <div className="border-t p-4">
        <div className="rounded-lg bg-muted p-3">
          <p className="text-xs font-medium">Need help?</p>
          <p className="text-xs text-muted-foreground mt-1">
            Check our documentation or contact support.
          </p>
        </div>
      </div>
    </div>
  )
}
