import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
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
  return (
    <div className="flex h-full w-64 flex-col bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-950 border-r">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-6 border-b">
        <img src="/favicon.ico" alt="PONTIS Logo" className="h-8 w-8" />
        <div>
          <span className="text-lg font-bold">PONTIS</span>
          <p className="text-xs text-muted-foreground">Recruitment System</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
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
        ))}
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
