import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useTheme } from '@/context/ThemeContext'
import { useAuth } from '@/context/AuthContext'
import { useToast } from '@/hooks/use-toast'
import api from '@/lib/api'
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
  Send
} from 'lucide-react'

const CLIENT_FILTER_STORAGE_KEY = 'selectedClientFilter'
const SUPPORT_EMAIL = 'info@pontis.one'
const SUPPORT_PHONE_PLACEHOLDER = 'Mobile number will be shared soon'

export function Sidebar() {
  const { theme } = useTheme()
  const { user } = useAuth()
  const { toast } = useToast()
  const location = useLocation()
  const isDark = theme === 'dark'
  const [isHelpOpen, setIsHelpOpen] = useState(false)
  const [fullName, setFullName] = useState('')
  const [emailAddress, setEmailAddress] = useState('')
  const [mobileNumber, setMobileNumber] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [emailSubject, setEmailSubject] = useState('')
  const [emailMessage, setEmailMessage] = useState('')
  const [isSendingHelpMessage, setIsSendingHelpMessage] = useState(false)
  
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

  const resetHelpForm = () => {
    setFullName('')
    setEmailAddress('')
    setMobileNumber('')
    setCompanyName('')
    setEmailSubject('')
    setEmailMessage('')
  }

  const handleSendEmail = async (event) => {
    event.preventDefault()

    const fullNameValue = fullName.trim()
    const emailAddressValue = emailAddress.trim()
    const mobileNumberValue = mobileNumber.trim()
    const companyNameValue = companyName.trim()
    const subject = emailSubject.trim()
    const message = emailMessage.trim()

    if (!fullNameValue || !emailAddressValue || !mobileNumberValue || !companyNameValue || !subject || !message) {
      return
    }

    try {
      setIsSendingHelpMessage(true)
      await api.post('/email/support', {
        full_name: fullNameValue,
        email_address: emailAddressValue,
        mobile_number: mobileNumberValue,
        company_name: companyNameValue,
        subject,
        message,
      })

      toast({
        title: 'Message sent',
        description: `Your message was sent to ${SUPPORT_EMAIL}.`,
      })
      setIsHelpOpen(false)
      resetHelpForm()
    } catch (error) {
      toast({
        title: 'Failed to send message',
        description: error.message || `Please try again or contact ${SUPPORT_EMAIL}.`,
      })
    } finally {
      setIsSendingHelpMessage(false)
    }
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
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-hidden border-slate-200 bg-white p-0 shadow-xl">
          <DialogHeader>
            <div className="border-b border-slate-200 px-6 py-5">
              <DialogTitle className="text-3xl font-bold text-slate-900">
                Send us a message
              </DialogTitle>
              <DialogDescription className="mt-2 text-base text-slate-500">
                Your message will be sent directly to {SUPPORT_EMAIL}.
              </DialogDescription>
              <p className="mt-2 text-sm text-slate-500">
                Mobile number: {SUPPORT_PHONE_PLACEHOLDER}
              </p>
            </div>
          </DialogHeader>

          <form
            onSubmit={handleSendEmail}
            className="max-h-[calc(90vh-112px)] space-y-5 overflow-y-auto px-6 py-6"
          >
            <div className="grid gap-5 md:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="support-full-name" className="text-sm font-medium text-slate-700">
                  Full Name
                </label>
                <Input
                  id="support-full-name"
                  placeholder="Enter your Full name"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  className="h-14 rounded-2xl border-slate-200 px-4 text-base"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="support-email-address" className="text-sm font-medium text-slate-700">
                  Email Address
                </label>
                <Input
                  id="support-email-address"
                  type="email"
                  placeholder="Enter your Email ID"
                  value={emailAddress}
                  onChange={(event) => setEmailAddress(event.target.value)}
                  className="h-14 rounded-2xl border-slate-200 px-4 text-base"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="support-mobile-number" className="text-sm font-medium text-slate-700">
                Mobile Number
              </label>
              <Input
                id="support-mobile-number"
                placeholder="Enter your Mobile Number"
                value={mobileNumber}
                onChange={(event) => setMobileNumber(event.target.value)}
                className="h-14 rounded-2xl border-slate-200 px-4 text-base"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="support-company-name" className="text-sm font-medium text-slate-700">
                Company
              </label>
              <Input
                id="support-company-name"
                placeholder="Company Name"
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
                className="h-14 rounded-2xl border-slate-200 px-4 text-base"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="support-subject" className="text-sm font-medium text-slate-700">
                Subject
              </label>
              <Input
                id="support-subject"
                placeholder="Enter your subject"
                value={emailSubject}
                onChange={(event) => setEmailSubject(event.target.value)}
                className="h-14 rounded-2xl border-slate-200 px-4 text-base"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="support-message" className="text-sm font-medium text-slate-700">
                Message
              </label>
              <Textarea
                id="support-message"
                placeholder="How can we help you?"
                value={emailMessage}
                onChange={(event) => setEmailMessage(event.target.value)}
                className="min-h-[140px] rounded-2xl border-slate-200 px-4 py-3 text-base"
              />
            </div>

            <div className="pb-1 pt-1">
              <Button
                type="submit"
                disabled={
                  isSendingHelpMessage ||
                  !fullName.trim() ||
                  !emailAddress.trim() ||
                  !mobileNumber.trim() ||
                  !companyName.trim() ||
                  !emailSubject.trim() ||
                  !emailMessage.trim()
                }
                className="h-14 w-full rounded-full text-lg font-semibold"
              >
                <Send className="mr-3 h-5 w-5" />
                {isSendingHelpMessage ? 'Sending...' : 'Send Message'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
