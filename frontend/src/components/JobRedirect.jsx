import { useEffect } from 'react'

const PUBLIC_JOBS_BASE_URL =
  import.meta.env.VITE_PUBLIC_JOBS_BASE_URL ||
  'https://ai-recruitment-dashboard-production.up.railway.app'

function JobRedirect() {
  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const { hostname, pathname, search, hash } = window.location
    const targetBaseUrl = new URL(PUBLIC_JOBS_BASE_URL)

    if (hostname === targetBaseUrl.hostname) {
      return
    }

    if (hostname !== 'pontis.one' && hostname !== 'www.pontis.one') {
      return
    }

    const redirectUrl = `${targetBaseUrl.origin}${pathname}${search}${hash}`
    window.location.replace(redirectUrl)
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6">
      <div className="text-center">
        <p className="text-lg font-medium text-foreground">Redirecting to job page...</p>
      </div>
    </div>
  )
}

export default JobRedirect
