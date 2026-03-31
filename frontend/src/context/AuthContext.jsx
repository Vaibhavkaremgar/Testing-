import { createContext, useContext, useState, useEffect, useRef } from 'react'
import { api } from '@/lib/api'

const AuthContext = createContext(null)
const INACTIVITY_LIMIT_MS = 30 * 60 * 1000
const LAST_ACTIVITY_KEY = 'lastActivityAt'

function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return null
  }
}

function getInitialUser() {
  const token = localStorage.getItem('token')
  if (!token) return null
  const payload = parseJwt(token)
  if (!payload) return null
  // New token format has role + user_id; old tokens only had sub + agency_id
  if (payload.role && payload.user_id) {
    return {
      id: payload.user_id,
      email: payload.sub,
      full_name: payload.full_name || '',
      role: payload.role,
      agency_id: payload.agency_id || null,
    }
  }
  // Old token — can't trust it, force getMe()
  return null
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getInitialUser)
  const [loading, setLoading] = useState(() => {
    // Only show loading spinner if we have a token but couldn't parse it (old format)
    const token = localStorage.getItem('token')
    if (!token) return false
    return getInitialUser() === null
  })
  const backgroundFetchDone = useRef(false)
  const inactivityTimeoutRef = useRef(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) return

    // Always refresh user data in background to get latest info
    if (!backgroundFetchDone.current) {
      backgroundFetchDone.current = true
      api.getMe()
        .then(userData => {
          setUser(userData)
        })
        .catch(error => {
          if (error.response?.status === 401 || error.message === 'Unauthorized') {
            localStorage.removeItem('token')
            setUser(null)
          }
          // On network errors (Railway cold start), keep existing user from JWT
        })
        .finally(() => {
          setLoading(false)
        })
    }
  }, [])

  const login = async (email, password) => {
    await api.login(email, password)
    const userData = await api.getMe()
    setUser(userData)
    return userData
  }

  const logout = () => {
    api.logout()
    localStorage.removeItem(LAST_ACTIVITY_KEY)
    setUser(null)
  }

  useEffect(() => {
    if (!user) {
      if (inactivityTimeoutRef.current) {
        clearTimeout(inactivityTimeoutRef.current)
        inactivityTimeoutRef.current = null
      }
      return
    }

    const markActivity = () => {
      localStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()))
    }

    const scheduleAutoLogout = () => {
      const lastActivityAt = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || Date.now())
      const elapsed = Date.now() - lastActivityAt
      const remaining = Math.max(INACTIVITY_LIMIT_MS - elapsed, 0)

      if (inactivityTimeoutRef.current) {
        clearTimeout(inactivityTimeoutRef.current)
      }

      inactivityTimeoutRef.current = setTimeout(() => {
        api.logout()
        localStorage.removeItem(LAST_ACTIVITY_KEY)
        setUser(null)
      }, remaining)
    }

    const handleActivity = () => {
      markActivity()
      scheduleAutoLogout()
    }

    const handleStorage = (event) => {
      if (event.key === LAST_ACTIVITY_KEY) {
        scheduleAutoLogout()
      }
      if (event.key === 'token' && !event.newValue) {
        setUser(null)
      }
    }

    if (!localStorage.getItem(LAST_ACTIVITY_KEY)) {
      markActivity()
    }
    scheduleAutoLogout()

    const activityEvents = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click']
    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, handleActivity, { passive: true })
    })
    window.addEventListener('storage', handleStorage)

    return () => {
      if (inactivityTimeoutRef.current) {
        clearTimeout(inactivityTimeoutRef.current)
        inactivityTimeoutRef.current = null
      }
      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, handleActivity)
      })
      window.removeEventListener('storage', handleStorage)
    }
  }, [user])

  const refreshUser = async () => {
    const userData = await api.getMe()
    setUser(userData)
    return userData
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, refreshUser, loading, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
