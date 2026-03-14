import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { User, Bell, Shield, Palette, Key, Save, Target } from 'lucide-react'

export default function Settings() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const [profileData, setProfileData] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
  })
  const [scoreSettings, setScoreSettings] = useState(() => {
    // Initialize with saved value from localStorage
    const savedScore = localStorage.getItem('minPassingScore')
    return {
      minPassingScore: savedScore ? parseInt(savedScore) : 70
    }
  })
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: ''
  })

  const handleProfileUpdate = async () => {
    if (!profileData.full_name.trim()) {
      alert('Please enter your full name')
      return
    }
    
    if (!profileData.email.trim()) {
      alert('Please enter your email')
      return
    }
    
    try {
      await api.updateProfile(profileData)
      // Refresh user data to update the header avatar
      window.location.reload()
      alert('Profile updated successfully!')
    } catch (error) {
      alert(error.message || 'Failed to update profile')
    }
  }

  const handleScoreSettingsUpdate = async () => {
    if (scoreSettings.minPassingScore < 0 || scoreSettings.minPassingScore > 100) {
      alert('Minimum passing score must be between 0 and 100')
      return
    }
    
    try {
      // Save to localStorage for immediate use
      localStorage.setItem('minPassingScore', scoreSettings.minPassingScore.toString())
      
      // Dispatch custom event to notify other components
      window.dispatchEvent(new CustomEvent('minPassingScoreChanged', {
        detail: { newScore: scoreSettings.minPassingScore }
      }))
      
      await api.saveResumeScoreSettings(scoreSettings)
      alert('Resume scoring settings updated successfully!')
    } catch (error) {
      // Even if API fails, localStorage will work
      localStorage.setItem('minPassingScore', scoreSettings.minPassingScore.toString())
      window.dispatchEvent(new CustomEvent('minPassingScoreChanged', {
        detail: { newScore: scoreSettings.minPassingScore }
      }))
      alert('Resume scoring settings updated successfully!')
    }
  }

  const handlePasswordUpdate = async () => {
    console.log('API object:', api)
    console.log('changePassword method:', api.changePassword)
    
    // Validate that both fields are filled
    if (!passwordData.currentPassword.trim()) {
      alert('Please enter your current password')
      return
    }
    
    if (!passwordData.newPassword.trim()) {
      alert('Please enter a new password')
      return
    }
    
    if (passwordData.newPassword.length < 6) {
      alert('New password must be at least 6 characters long')
      return
    }
    
    try {
      const response = await api.changePassword(passwordData.currentPassword, passwordData.newPassword)
      alert('Password updated successfully! You will be logged out. Please login with your new password.')
      setPasswordData({ currentPassword: '', newPassword: '' })
      
      // Logout user and redirect to login page
      setTimeout(() => {
        logout()
        navigate('/login')
      }, 1000)
    } catch (error) {
      alert(error.message || 'Failed to update password')
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your account and preferences</p>
      </div>

      {/* Profile */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <User className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">Profile</CardTitle>
              <CardDescription>Your personal information</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Full Name</label>
              <Input
                value={profileData.full_name}
                onChange={(e) => setProfileData({ ...profileData, full_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email</label>
              <Input
                type="email"
                value={profileData.email}
                onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Role:</span>
            <Badge variant="secondary" className="capitalize">{user?.role}</Badge>
          </div>
          <Button onClick={handleProfileUpdate}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </CardContent>
      </Card>

      {/* Resume Scoring - REMOVED */}

      {/* Appearance */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Palette className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">Appearance</CardTitle>
              <CardDescription>Customize how HireFlow looks</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <label className="text-sm font-medium">Theme</label>
            <div className="flex gap-2">
              {['light', 'dark'].map((t) => (
                <Button
                  key={t}
                  variant={theme === t ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setTheme(t)}
                  className="capitalize"
                >
                  {t}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Bell className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">Notifications</CardTitle>
              <CardDescription>Configure notification preferences</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {[
            { label: 'New candidate applications', description: 'Get notified when new resumes are uploaded' },
            { label: 'Interview reminders', description: 'Receive reminders before scheduled interviews' },
            { label: 'AI analysis complete', description: 'Get notified when resume/interview analysis is ready' },
            { label: 'Weekly reports', description: 'Receive weekly hiring pipeline summaries' },
          ].map((item, index) => (
            <div key={index} className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{item.label}</p>
                <p className="text-xs text-muted-foreground">{item.description}</p>
              </div>
              <input
                type="checkbox"
                defaultChecked={index < 2}
                className="h-4 w-4 rounded border-input"
              />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Security */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            {/*<div className="p-2 rounded-lg bg-primary/10">
              <Shield className="h-5 w-5 text-primary" />
            </div>*/}
            <div>
              <CardTitle className="text-base">Security</CardTitle>
              <CardDescription>Manage your security settings</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Change Password</label>
            <div className="grid grid-cols-2 gap-4">
              <Input 
                type="password" 
                placeholder="Current password"
                value={passwordData.currentPassword}
                onChange={(e) => setPasswordData({...passwordData, currentPassword: e.target.value})}
              />
              <Input 
                type="password" 
                placeholder="New password"
                value={passwordData.newPassword}
                onChange={(e) => setPasswordData({...passwordData, newPassword: e.target.value})}
              />
            </div>
          </div>
          {/*<Button variant="outline" onClick={handlePasswordUpdate}>
            <Key className="h-4 w-4 mr-2" />
            Update Password
          </Button>*/}
          <Button variant="outline" onClick={handlePasswordUpdate}>
            Update Password
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
