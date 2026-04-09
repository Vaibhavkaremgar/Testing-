import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, Clock3, RefreshCw, ShieldCheck, Video, Waves } from 'lucide-react'

import VideoPlayer from '@/components/VideoPlayer'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const LOAD_TIMEOUT_MS = 15000
const RETRY_DELAY_MS = 500

function normalizeSessionToken(value) {
  return String(value || '')
    .trim()
    .replace(/\.(mp4|webm)$/i, '')
}

function buildRecordingUrls({ sessionToken, interviewId, asyncToken, recordingPath }) {
  const urls = []
  const normalizedSessionToken = normalizeSessionToken(sessionToken)
  const normalizedAsyncToken = normalizeSessionToken(asyncToken)
  const normalizedInterviewId = String(interviewId || '').trim()

  if (normalizedSessionToken) {
    try {
      urls.push(api.getDashboardRecordingUrl(normalizedSessionToken))
    } catch {
      // Ignore invalid URL construction.
    }
  }

  if (normalizedAsyncToken) {
    try {
      urls.push(api.getDashboardRecordingUrl(normalizedAsyncToken))
    } catch {
      // Ignore invalid URL construction.
    }
  }

  if (normalizedInterviewId) {
    try {
      urls.push(api.getInterviewVideoUrl(normalizedInterviewId))
    } catch {
      // Ignore invalid URL construction.
    }
  }

  return Array.from(new Set(urls.filter(Boolean)))
}

function inferVideoMimeType(recordingPath) {
  const normalizedPath = String(recordingPath || '').trim().toLowerCase()
  if (normalizedPath.endsWith('.webm')) {
    return 'video/webm'
  }
  if (normalizedPath.endsWith('.mp4')) {
    return 'video/mp4'
  }
  return undefined
}

function buildAuthorizedRecordingSources(videoUrl, recordingPath, token) {
  if (!videoUrl) {
    return []
  }

  const mimeType = inferVideoMimeType(recordingPath) || 'video/webm'
  const source = {
    src: videoUrl,
    type: mimeType,
    withCredentials: true,
  }

  if (token) {
    source.headers = {
      Authorization: `Bearer ${token}`,
    }
  }

  return [source]
}

function getPlayerErrorMessage(error) {
  if (error?.code === 4) {
    return 'Recording not available or not ready yet'
  }

  return 'Unable to load interview recording'
}

function describeFormat(recordingPath) {
  const mimeType = inferVideoMimeType(recordingPath)
  if (mimeType === 'video/webm') {
    return 'WEBM'
  }
  if (mimeType === 'video/mp4') {
    return 'MP4'
  }
  return 'AUTO'
}

function describeAvailability(status) {
  switch (status) {
    case 'available':
      return 'Ready to review'
    case 'checking':
      return 'Checking stream'
    case 'maybe_invalid':
      return 'Playable, verify response'
    case 'not_found':
      return 'Recording missing'
    case 'invalid':
      return 'Invalid source'
    default:
      return 'Stream status pending'
  }
}

export default function InterviewRecordingPlayer({
  sessionToken,
  interviewId,
  asyncToken,
  recordingPath,
  className,
  poster = '',
}) {
  const [isInitializing, setIsInitializing] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [isRetryPending, setIsRetryPending] = useState(false)
  const [availabilityStatus, setAvailabilityStatus] = useState('idle')
  const [activeUrlIndex, setActiveUrlIndex] = useState(0)
  const loadTimeoutRef = useRef(null)
  const retryTimeoutRef = useRef(null)
  const validationAbortRef = useRef(null)

  const candidateUrls = useMemo(
    () => buildRecordingUrls({ sessionToken, interviewId, asyncToken, recordingPath }),
    [asyncToken, interviewId, recordingPath, sessionToken]
  )
  const videoUrl = candidateUrls[activeUrlIndex] || ''
  const authToken = useMemo(() => api.getToken(), [])
  console.log('FINAL VIDEO URL:', videoUrl)
  const sources = useMemo(
    () => buildAuthorizedRecordingSources(videoUrl, recordingPath, authToken),
    [authToken, recordingPath, videoUrl]
  )
  const hasRecording = Boolean(videoUrl)
  const formatLabel = useMemo(() => describeFormat(recordingPath), [recordingPath])
  const availabilityLabel = useMemo(() => describeAvailability(availabilityStatus), [availabilityStatus])
  const sourceCount = candidateUrls.length
  const hasValidRecordingPath = (
    (typeof sessionToken === 'string' && sessionToken.trim().length > 0)
    || (typeof interviewId === 'string' && interviewId.trim().length > 0)
    || (typeof asyncToken === 'string' && asyncToken.trim().length > 0)
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

  const tryNextSource = () => {
    if (activeUrlIndex < candidateUrls.length - 1) {
      clearLoadTimeout()
      clearValidationRequest()
      setErrorMessage('')
      setAvailabilityStatus('checking')
      setIsInitializing(true)
      setActiveUrlIndex((currentIndex) => currentIndex + 1)
      return true
    }

    return false
  }

  useEffect(() => {
    setActiveUrlIndex(0)
  }, [candidateUrls])

  
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

    // HEAD validation is only a UX hint. Some upstream recording services do
    // not support HEAD for protected assets even when GET playback works.
    fetch(videoUrl, {
      headers: authToken ? {
        Authorization: `Bearer ${authToken}`,
      } : undefined,
      method: 'HEAD',
      signal: abortController.signal,
      credentials: 'include',
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

        if (response.ok) {
          if (contentType && !contentType.toLowerCase().includes('video')) {
            setAvailabilityStatus('maybe_invalid')
          } else {
            setAvailabilityStatus('available')
          }
          return
        }

        if (response.status === 404) {
          console.info('Interview recording HEAD returned 404; continuing with playback attempt.', {
            recordingPath,
            sessionToken,
            videoUrl,
          })
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
  }, [activeUrlIndex, asyncToken, authToken, candidateUrls.length, hasRecording, hasValidRecordingPath, interviewId, recordingPath, retryKey, sessionToken, videoUrl])

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

    if (playerError?.code === 4 && tryNextSource()) {
      return
    }

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
    <div className={cn('interview-recording-player-shell relative h-full w-full overflow-hidden rounded-[1.5rem] border border-slate-800/80 bg-[#040816]', className)}>
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-4 p-4">
        <div className="max-w-[70%] rounded-2xl border border-white/10 bg-slate-950/55 px-4 py-3 text-white shadow-2xl backdrop-blur-md">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-200/90">
            <Waves className="h-3.5 w-3.5" />
            Interview Recording
          </div>
          <p className="mt-2 text-base font-semibold text-white">Review candidate playback with upgraded controls</p>
          <p className="mt-1 text-xs text-slate-300/80">{availabilityLabel}</p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Badge className="border border-emerald-400/30 bg-emerald-500/15 px-3 py-1 text-[11px] font-medium text-emerald-100 shadow-sm backdrop-blur-md hover:bg-emerald-500/15">
            <ShieldCheck className="mr-1 h-3.5 w-3.5" />
            Protected stream
          </Badge>
          <Badge className="border border-cyan-400/25 bg-cyan-400/10 px-3 py-1 text-[11px] font-medium text-cyan-100 shadow-sm backdrop-blur-md hover:bg-cyan-400/10">
            <Video className="mr-1 h-3.5 w-3.5" />
            {formatLabel}
          </Badge>
          <Badge className="border border-white/10 bg-white/10 px-3 py-1 text-[11px] font-medium text-slate-100 shadow-sm backdrop-blur-md hover:bg-white/10">
            <Clock3 className="mr-1 h-3.5 w-3.5" />
            {sourceCount > 1 ? `${activeUrlIndex + 1}/${sourceCount} sources` : 'Single source'}
          </Badge>
        </div>
      </div>

      {shouldRenderPlayer && !errorMessage ? (
        <VideoPlayer
          key={`${videoUrl}-${retryKey}`}
          sources={sources}
          poster={poster}
          preload="metadata"
          playsInline
          className="h-full w-full rounded-[1.5rem]"
          videoClassName="object-contain"
          options={{
            controls: true,
            fluid: true,
            responsive: true,
            playbackRates: [0.75, 1, 1.25, 1.5, 2],
            userActions: {
              hotkeys: true,
            },
            controlBar: {
              remainingTimeDisplay: {
                displayNegative: false,
              },
              skipButtons: {
                backward: 10,
                forward: 10,
              },
              volumePanel: {
                inline: false,
              },
              pictureInPictureToggle: false,
            },
          }}
          onLoadedData={handlePlayerReady}
          onCanPlay={handlePlayerReady}
          onError={handlePlayerError}
        />
      ) : null}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex items-end justify-between gap-4 bg-gradient-to-t from-slate-950 via-slate-950/55 to-transparent px-5 pb-4 pt-12 text-white">
        <div>
          <p className="text-sm font-medium">Session playback</p>
          <p className="text-xs text-slate-300/75">Use speed controls, seek shortcuts, and fallback sources when available.</p>
        </div>
        <div className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-[11px] font-medium text-slate-200/90 backdrop-blur-md">
          {hasRecording ? 'Streaming via video.js' : 'Waiting for source'}
        </div>
      </div>

      {isInitializing && !errorMessage && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/72 text-white backdrop-blur-sm">
          <RefreshCw className="h-8 w-8 animate-spin" />
          <p className="text-sm font-medium">Loading recording...</p>
        </div>
      )}

      {errorMessage ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 rounded-[1.5rem] bg-slate-950/84 px-6 text-center text-white backdrop-blur-sm">
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
