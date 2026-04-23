import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useTheme } from '@/context/ThemeContext'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  LayoutDashboard,
  FileText,
  Users,
  Video,
  BarChart3,
  Settings,
  Briefcase,
  Mail,
  Building2,
  MessageSquare,
  UserCog,
  User as UserIcon,
  Wallet,
  ShieldCheck,
  Tag,
  Phone,
  Send
} from 'lucide-react'

const CLIENT_FILTER_STORAGE_KEY = 'selectedClientFilter'
const SUPPORT_EMAIL = 'info@pontis.one'
const SUPPORT_PHONE_PLACEHOLDER = 'Mobile number will be shared soon'
const HELP_FAQS = [
  {
    question: 'How do I start from the dashboard?',
    answer: 'Use the dashboard as your quick overview. From there, you can jump into jobs, resumes, candidates, interviews, communications, and other day-to-day actions.'
  },
  {
    question: 'Why am I not seeing some menu options?',
    answer: 'The sidebar changes based on your role. Admins and super admins can see more management sections, while non-admin users see the areas assigned to their workflow.'
  },
  {
    question: 'How can I track candidates faster?',
    answer: 'Open the candidates or pipeline section from the sidebar to review stages, move applicants through the process, and keep your hiring flow organized.'
  },
  {
    question: 'Where can I manage communications and interviews?',
    answer: 'You can use the Communications section for messages and the Interviews section to manage interview activity and follow-up actions.'
  },
  {
    question: 'Who should I contact if something is unclear?',
    answer: 'Use the support details in this help window to contact the Pontis team with your subject and message.'
  }
]

export function Sidebar() {
  const { theme } = useTheme()
  const { user } = useAuth()
  const location = useLocation()
  const isDark = theme === 'dark'
  const [isHelpOpen, setIsHelpOpen] = useState(false)
  const [emailSubject, setEmailSubject] = useState('')
  const [emailMessage, setEmailMessage] = useState('')
  
  // Role-based navigation
  const getNavigation = () => {
    const isAdmin = user?.role === 'admin'
    const isSuperAdmin = user?.role === 'super_admin'

    if (isSuperAdmin) {
      return [
        { name: 'Dashboard', href: '/super-admin', icon: LayoutDashboard },
        { name: 'Agencies', href: '/super-admin/agencies', icon: ShieldCheck },
        { name: 'Jobs', href: '/super-admin/jobs', icon: Briefcase },
        { name: 'Candidates', href: '/super-admin/candidates', icon: Users },
        { name: 'Interviews', href: '/super-admin/interviews', icon: Video },
        { name: 'Clients', href: '/super-admin/clients', icon: Building2 },
        { name: 'Users', href: '/super-admin/users', icon: UserCog },
        { name: 'Pricing', href: '/super-admin/pricing', icon: Tag },
        { name: 'Settings', href: '/super-admin/settings', icon: Settings },
      ]
    }

    // Admin sees everything
    if (isAdmin) {
      return [
        { name: 'Dashboard', href: '/', icon: LayoutDashboard },
        { name: 'Jobs', href: '/jobs', icon: Briefcase },
        { name: 'Resumes', href: '/resumes', icon: FileText },
        { name: 'Candidates', href: '/pipeline', icon: Users },
        { name: 'Interviews', href: '/interviews', icon: Video },
        { name: 'Clients', href: '/clients', icon: Building2 },
        { name: 'Analytics', href: '/analytics', icon: BarChart3 },
        { name: 'Communications', href: '/communications', icon: MessageSquare },
        { name: 'Wallet', href: '/wallet', icon: Wallet },
        { name: 'Settings', href: '/settings', icon: Settings },
        { name: 'Users', href: '/admin/users', icon: UserCog },
      ]
    }
    
    // Regular users see My Assignments
    return [
      { name: 'Dashboard', href: '/', icon: LayoutDashboard },
      { name: 'Resumes', href: '/my-assignments', icon: FileText },
      { name: 'Jobs', href: '/jobs', icon: Briefcase },
      { name: 'Candidates', href: '/pipeline', icon: Users },
      { name: 'Interviews', href: '/interviews', icon: Video },
      { name: 'Communications', href: '/communications', icon: MessageSquare },
      { name: 'Email Customization', href: '/email-templates', icon: Mail },
      { name: 'Profile', href: '/profile', icon: UserIcon },
    ]
  }
  
  const navigation = getNavigation()
  const activeClient = new URLSearchParams(location.search).get('client') || localStorage.getItem(CLIENT_FILTER_STORAGE_KEY) || ''
  const buildNavTarget = (href) => activeClient ? `${href}?client=${encodeURIComponent(activeClient)}` : href

  const handleSendEmail = () => {
    const subject = emailSubject.trim()
    const message = emailMessage.trim()

    if (!subject || !message) {
      return
    }

    const mailtoLink = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(message)}`
    window.location.href = mailtoLink
  }
  
  return (
    <>
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
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={buildNavTarget(item.href)}
              end={item.href === '/' || item.href === '/super-admin'}
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
          <button
            type="button"
            onClick={() => setIsHelpOpen(true)}
            className="w-full rounded-lg bg-muted p-3 text-left transition-colors hover:bg-accent"
          >
            <p className="text-xs font-medium">Need help?</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Open support questions, contact details, and email help.
            </p>
          </button>
        </div>
      </div>

      <Dialog open={isHelpOpen} onOpenChange={setIsHelpOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Help & Support</DialogTitle>
            <DialogDescription>
              Find quick dashboard answers and contact the Pontis support team.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Mail className="h-4 w-4" />
                  Support email
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{SUPPORT_EMAIL}</p>
              </div>

              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Phone className="h-4 w-4" />
                  Contact number
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{SUPPORT_PHONE_PLACEHOLDER}</p>
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Frequently asked questions</h3>
              <div className="space-y-3">
                {HELP_FAQS.map((item) => (
                  <div key={item.question} className="rounded-lg border p-4">
                    <p className="text-sm font-medium">{item.question}</p>
                    <p className="mt-2 text-sm text-muted-foreground">{item.answer}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4 rounded-lg border p-4">
              <div>
                <h3 className="text-sm font-semibold">Send email</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Your email app will open with a draft addressed to {SUPPORT_EMAIL}.
                </p>
              </div>

              <div className="space-y-2">
                <label htmlFor="support-email" className="text-sm font-medium">To</label>
                <Input id="support-email" value={SUPPORT_EMAIL} readOnly />
              </div>

              <div className="space-y-2">
                <label htmlFor="support-subject" className="text-sm font-medium">Subject</label>
                <Input
                  id="support-subject"
                  placeholder="Enter your subject"
                  value={emailSubject}
                  onChange={(event) => setEmailSubject(event.target.value)}
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="support-message" className="text-sm font-medium">Message</label>
                <Textarea
                  id="support-message"
                  placeholder="Write your message here"
                  value={emailMessage}
                  onChange={(event) => setEmailMessage(event.target.value)}
                  className="min-h-[140px]"
                />
              </div>

              <Button
                type="button"
                onClick={handleSendEmail}
                disabled={!emailSubject.trim() || !emailMessage.trim()}
                className="w-full"
              >
                <Send className="mr-2 h-4 w-4" />
                Send
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
