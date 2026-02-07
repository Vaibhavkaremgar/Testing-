import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export function LoadingSpinner({ className, size = 'default', ...props }) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    default: 'h-6 w-6',
    lg: 'h-8 w-8',
    xl: 'h-12 w-12'
  }

  return (
    <Loader2 
      className={cn('animate-spin', sizeClasses[size], className)} 
      {...props} 
    />
  )
}

export function LoadingPage({ message = 'Loading...' }) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-4">
        <LoadingSpinner size="xl" className="mx-auto text-primary" />
        <p className="text-muted-foreground">{message}</p>
      </div>
    </div>
  )
}

export function LoadingCard({ message = 'Loading...', className }) {
  return (
    <div className={cn('flex items-center justify-center p-8', className)}>
      <div className="text-center space-y-3">
        <LoadingSpinner size="lg" className="mx-auto text-primary" />
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  )
}