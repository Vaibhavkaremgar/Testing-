import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, RefreshCw, Video } from 'lucide-react'

import VideoPlayer from '@/components/VideoPlayer'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const DEFAULT_RECORDING_API_BASE = 'https://interview.pontis.one/api/recording'
const LOAD_TIMEOUT_MS = 15000
const RETRY_DELAY_MS = 500

function buildRecordingUrl(recordingPath) {
  const normalizedToken = String(recordingPath || '').trim()
  if (!normalizedToken) {
    return ''
  }

  return `${DEFAULT_RECORDING_API_BASE}/${encodeURIComponent(normalizedToken)}`
}

function buildRecordingSources(videoUrl) {
  if (!videoUrl) {
    return []
  }

  // Pass a single source without a forced MIME type so the backend response
  // headers determine the format.
  return [{ src: videoUrl }]
}

function getPlayerErrorMessage(error) {
  if (error?.code === 4) {
    return 'Recording Not Found'
  }

  return 'Unable to load interview recording.'
}

export default function InterviewRecordingPlayer({
  recordingPath,
  className,
  poster = '',
}) {
  const [isInitializing, setIsInitializing] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [isRetryPending, setIsRetryPending] = useState(false)
  const loadTimeoutRef = useRef(null)
  const retryTimeoutRef = useRef(null)

  const videoUrl = useMemo(() => buildRecordingUrl(recordingPath), [recordingPath])
  const sources = useMemo(() => buildRecordingSources(videoUrl), [videoUrl])
  const hasRecording = Boolean(videoUrl)

  const clearLoadTimeout = () => {
    if (loadTimeoutRef.current) {
      clearTimeout(loadTimeoutRef.current)
      loadTimeoutRef.current = null
    }
  }

  const clearRetryTimeout = () => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }
  }

  useEffect(() => {
    clearLoadTimeout()
    clearRetryTimeout()
    setErrorMessage('')
    setIsRetryPending(false)
    setIsInitializing(hasRecording)

    if (!hasRecording) {
      return undefined
    }

    // Fail fast when the recording service is slow or unreachable so the UI
    // doesn't remain stuck in a spinner forever.
    loadTimeoutRef.current = setTimeout(() => {
      setIsInitializing(false)
      setErrorMessage('Recording load timeout')
    }, LOAD_TIMEOUT_MS)

    return () => {
      clearLoadTimeout()
      clearRetryTimeout()
    }
  }, [hasRecording, retryKey, videoUrl])

  useEffect(() => () => {
    clearLoadTimeout()
    clearRetryTimeout()
  }, [])

  const handlePlayerReady = () => {
    clearLoadTimeout()
    setIsInitializing(false)
    setErrorMessage('')
  }

  const handlePlayerError = (player) => {
    const playerError = player?.error?.()

    clearLoadTimeout()
    setIsInitializing(false)
    setErrorMessage(getPlayerErrorMessage(playerError))

    console.error('Interview recording player error:', {
      recordingPath,
      videoUrl,
      error: playerError,
      currentSource: player?.currentSource?.(),
      currentSources: player?.currentSources?.(),
    })
  }

  const handleRetry = () => {
    clearLoadTimeout()
    clearRetryTimeout()
    setErrorMessage('')
    setIsInitializing(false)
    setIsRetryPending(true)

    retryTimeoutRef.current = setTimeout(() => {
      setIsRetryPending(false)
      setRetryKey((value) => value + 1)
    }, RETRY_DELAY_MS)
  }

  if (!recordingPath) {
    return (
      <div className={cn('flex h-full w-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border/70 bg-muted/20 p-6 text-center', className)}>
        <Video className="h-12 w-12 opacity-40" />
        <div>
          <p className="font-medium">No Recording Available</p>
          <p className="text-sm text-muted-foreground">This interview session does not have a recording yet.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('relative h-full w-full rounded-xl border bg-black/95', className)}>
      {!errorMessage ? (
        <VideoPlayer
          key={`${videoUrl}-${retryKey}`}
          sources={sources}
          poster={poster}
          preload="metadata"
          playsInline
          className="h-full w-full rounded-xl"
          videoClassName="object-contain"
          options={{
            controls: true,
            fluid: true,
            responsive: true,
            controlBar: {
              pictureInPictureToggle: false,
            },
          }}
          onLoadedData={handlePlayerReady}
          onCanPlay={handlePlayerReady}
          onError={handlePlayerError}
        />
      ) : null}

      {isInitializing && !errorMessage && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/70 text-white">
          <RefreshCw className="h-8 w-8 animate-spin" />
          <p className="text-sm font-medium">Loading recording...</p>
        </div>
      )}

      {errorMessage ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 rounded-xl bg-black/80 px-6 text-center text-white">
          <AlertCircle className="h-12 w-12 text-amber-300" />
          <div>
            <p className="text-lg font-semibold">{errorMessage}</p>
            <p className="mt-1 text-sm text-white/70">
              {errorMessage === 'Recording Not Found'
                ? 'The recording endpoint returned 404 for this session token.'
                : 'Please try again. If the issue persists, verify the recording service and session token.'}
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            disabled={isRetryPending}
            onClick={handleRetry}
          >
            {isRetryPending ? 'Retrying...' : 'Retry'}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
