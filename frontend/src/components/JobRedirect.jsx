import { useEffect } from 'react'

const PUBLIC_JOBS_BASE_URL =
  import.meta.env.VITE_PUBLIC_JOBS_BASE_URL ||
  'https://ai-recruitment-dashboard-production.up.railway.app'

export default function JobRedirect() {
  useEffect(() => {
    if (typeof window === 'undefined') return

    console.log('Job redirect triggered')

    const { hostname, pathname, search, hash } = window.location
    const targetBaseUrl = new URL(PUBLIC_JOBS_BASE_URL)

    if (hostname === targetBaseUrl.hostname) return

    const redirectUrl = `${targetBaseUrl.origin}${pathname}${search}${hash}`

    console.log('Redirecting to:', redirectUrl)

    window.location.href = redirectUrl
  }, [])

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontSize: '20px',
      }}
    >
      Redirecting to job page...
    </div>
  )
}
