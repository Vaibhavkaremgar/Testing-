import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, RefreshCw, Video } from 'lucide-react'

import VideoPlayer from '@/components/VideoPlayer'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const LOAD_TIMEOUT_MS = 15000
const RETRY_DELAY_MS = 500

function buildRecordingUrl(sessionToken, recordingPath) {
  const normalizedToken = String(sessionToken || recordingPath || '').trim()
  if (!normalizedToken) {
    return ''
  }

  try {
    return api.getDashboardRecordingUrl(normalizedToken)
  } catch {
    return ''
  }
}

function buildRecordingSources(videoUrl) {
  if (!videoUrl) {
    return []
  }

  // The proxy serves either MP4 or WebM based on the stored recording.
  // Use a broad video fallback so video.js accepts either container while the
  // browser still relies on the response Content-Type from the backend.
  return [{ src: videoUrl, type: 'video/*' }]
}

function getPlayerErrorMessage(error) {
  if (error?.code === 4) {
    return 'Recording not available or not ready yet'
  }

  return 'Unable to load interview recording'
}

export default function InterviewRecordingPlayer({
  sessionToken,
  recordingPath,
  className,
  poster = '',
}) {
  const [isInitializing, setIsInitializing] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [isRetryPending, setIsRetryPending] = useState(false)
  const [availabilityStatus, setAvailabilityStatus] = useState('idle')
  const loadTimeoutRef = useRef(null)
  const retryTimeoutRef = useRef(null)
  const validationAbortRef = useRef(null)

  const videoUrl = useMemo(
    () => buildRecordingUrl(sessionToken, recordingPath),
    [recordingPath, sessionToken]
  )
  const sources = useMemo(() => buildRecordingSources(videoUrl), [videoUrl])
  const hasRecording = Boolean(videoUrl)
  const hasValidRecordingPath = (
    (typeof sessionToken === 'string' && sessionToken.trim().length > 0)
    || (typeof recordingPath === 'string' && recordingPath.trim().length > 0)
  )

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

  const clearValidationRequest = () => {
    if (validationAbortRef.current) {
      validationAbortRef.current.abort()
      validationAbortRef.current = null
    }
  }

  useEffect(() => {
    clearLoadTimeout()
    clearRetryTimeout()
    clearValidationRequest()
    setErrorMessage('')
    setIsRetryPending(false)
    setAvailabilityStatus(hasRecording ? 'checking' : 'idle')
    setIsInitializing(hasRecording)

    if (!hasValidRecordingPath) {
      setIsInitializing(false)
      return undefined
    }

    if (!hasRecording) {
      setIsInitializing(false)
      setAvailabilityStatus('invalid')
      setErrorMessage('Invalid recording URL')
      return undefined
    }

    const abortController = new AbortController()
    validationAbortRef.current = abortController

    // Validate the URL before player startup so unsupported server responses
    // fail with a clear message instead of a generic media error.
    fetch(videoUrl, {
      method: 'HEAD',
      signal: abortController.signal,
    })
      .then((response) => {
        const contentType = response.headers.get('content-type') || ''

        console.info('Interview recording HEAD validation:', {
          recordingPath,
          sessionToken,
          videoUrl,
          status: response.status,
          contentType,
        })

        if (response.status === 404) {
          clearLoadTimeout()
          setIsInitializing(false)
          setAvailabilityStatus('not_found')
          setErrorMessage('Recording Not Found')
          return
        }

        if (response.ok) {
          if (contentType && !contentType.toLowerCase().includes('video')) {
            setAvailabilityStatus('maybe_invalid')
          } else {
            setAvailabilityStatus('available')
          }
          return
        }

        setAvailabilityStatus('unknown')
      })
      .catch((error) => {
        if (error?.name === 'AbortError') {
          return
        }

        // HEAD validation is only a UX hint. Ignore network/CORS failures and
        // let the player attempt real playback with the same URL.
        console.info('Interview recording HEAD validation skipped:', {
          recordingPath,
          sessionToken,
          videoUrl,
          errorMessage: error?.message,
          errorName: error?.name,
        })
        setAvailabilityStatus('unknown')
      })

    // Fail fast when the recording service is slow or unreachable so the UI
    // doesn't remain stuck in a spinner forever.
    loadTimeoutRef.current = setTimeout(() => {
      setIsInitializing(false)
      setErrorMessage('Recording load timeout')
    }, LOAD_TIMEOUT_MS)

    return () => {
      clearLoadTimeout()
      clearRetryTimeout()
      clearValidationRequest()
    }
  }, [hasRecording, hasValidRecordingPath, recordingPath, retryKey, sessionToken, videoUrl])

  useEffect(() => () => {
    clearLoadTimeout()
    clearRetryTimeout()
    clearValidationRequest()
  }, [])

  const handlePlayerReady = () => {
    clearLoadTimeout()
    setIsInitializing(false)
    setAvailabilityStatus('available')
    setErrorMessage('')
  }

  const handlePlayerError = (player) => {
    const playerError = player?.error?.()

    clearLoadTimeout()
    setIsInitializing(false)
    setErrorMessage(getPlayerErrorMessage(playerError))

    console.error('Video playback error:', {
      recordingPath,
      sessionToken,
      videoUrl,
      code: playerError?.code,
      message: playerError?.message,
      error: playerError,
      currentSource: player?.currentSource?.(),
      currentSources: player?.currentSources?.(),
      currentSrc: player?.currentSrc?.(),
      networkState: player?.networkState?.(),
      readyState: player?.readyState?.(),
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

  if (!hasValidRecordingPath) {
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

  const shouldRenderPlayer = hasRecording && availabilityStatus !== 'not_found'

  return (
    <div className={cn('relative h-full w-full rounded-xl border bg-black/95', className)}>
      {shouldRenderPlayer && !errorMessage ? (
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
                : errorMessage === 'Recording not available or not ready yet'
                  ? 'The recording is not available yet or is still being prepared for playback.'
                  : errorMessage === 'Server error while fetching recording'
                    ? 'The recording service returned a server error. Please retry shortly.'
                    : errorMessage === 'Unsupported media format'
                      ? 'The recording endpoint responded, but not with a browser-supported video content type.'
                      : errorMessage === 'Invalid video response from server'
                        ? 'The recording endpoint responded with an unexpected status or content type.'
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
