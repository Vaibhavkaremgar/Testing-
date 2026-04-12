import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, Video } from 'lucide-react'

import VideoPlayer from '@/components/VideoPlayer'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const LOAD_TIMEOUT_MS = 30000
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
  const normalizedRecordingPath = String(recordingPath || '').trim()

  const appendSource = (url, label) => {
    if (!url) {
      return
    }
    urls.push({ url, label })
  }

  if (normalizedRecordingPath) {
    try {
      appendSource(api.getUploadedRecordingUrl(normalizedRecordingPath), 'uploaded_recording_path')
    } catch {
      // Ignore invalid URL construction.
    }
  }

  if (normalizedSessionToken) {
    try {
      appendSource(api.getDashboardRecordingUrl(normalizedSessionToken), 'session_token_proxy')
    } catch {
      // Ignore invalid URL construction.
    }
  }

  if (normalizedAsyncToken) {
    try {
      appendSource(api.getDashboardRecordingUrl(normalizedAsyncToken), 'async_token_proxy')
    } catch {
      // Ignore invalid URL construction.
    }
  }

  if (normalizedInterviewId) {
    try {
      appendSource(api.getInterviewVideoUrl(normalizedInterviewId), 'interview_id_proxy')
    } catch {
      // Ignore invalid URL construction.
    }
  }

  const seenUrls = new Set()
  return urls.filter(({ url }) => {
    if (!url || seenUrls.has(url)) {
      return false
    }
    seenUrls.add(url)
    return true
  })
}

function inferVideoMimeType(recordingPath, recordingFormat) {
  const normalizedPath = String(recordingPath || '').trim().toLowerCase()
  if (normalizedPath.endsWith('.webm')) {
    return 'video/webm'
  }
  if (normalizedPath.endsWith('.mp4')) {
    return 'video/mp4'
  }
  const normalizedFormat = String(recordingFormat || '').trim().toLowerCase()
  if (normalizedFormat === 'webm') {
    return 'video/webm'
  }
  if (normalizedFormat === 'mp4') {
    return 'video/mp4'
  }
  return undefined
}

function buildAuthorizedRecordingSources(videoUrl, recordingPath, recordingFormat, token) {
  if (!videoUrl) {
    return []
  }

  const mimeType = inferVideoMimeType(recordingPath, recordingFormat)
  const source = {
    src: videoUrl,
    withCredentials: true,
  }

  if (mimeType) {
    source.type = mimeType
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

function summarizeProbeResult(result) {
  if (!result) {
    return 'Unknown probe failure'
  }

  if (result.error) {
    return `${result.label}: ${result.error}`
  }

  const statusPart = typeof result.status === 'number' ? `status ${result.status}` : 'no status'
  const typePart = result.contentType ? `content-type ${result.contentType}` : 'no content-type'
  return `${result.label}: ${statusPart}, ${typePart}`
}

async function probeRecordingSource(source, authToken, signal) {
  const headers = authToken ? { Authorization: `Bearer ${authToken}` } : undefined
  const methods = ['HEAD', 'GET']
  let lastResult = null

  for (const method of methods) {
    try {
      const response = await fetch(source.url, {
        method,
        headers: method === 'GET'
          ? {
            ...(headers || {}),
            Range: 'bytes=0-0',
          }
          : headers,
        credentials: 'include',
        signal,
      })

      const contentType = (response.headers.get('content-type') || '').toLowerCase()
      const contentLength = response.headers.get('content-length') || ''
      const acceptsRanges = response.headers.get('accept-ranges') || ''
      const isVideoLike = (
        contentType.includes('video/')
        || contentType.includes('application/octet-stream')
      )

      lastResult = {
        ok: response.ok && isVideoLike,
        method,
        label: source.label,
        url: source.url,
        status: response.status,
        contentType,
        contentLength,
        acceptsRanges,
        reason: response.ok
          ? (isVideoLike ? 'playable_video_response' : 'non_video_content_type')
          : 'non_success_status',
      }

      if (lastResult.ok) {
        return lastResult
      }
    } catch (error) {
      if (error?.name === 'AbortError') {
        throw error
      }

      lastResult = {
        ok: false,
        method,
        label: source.label,
        url: source.url,
        error: `${error?.name || 'Error'}: ${error?.message || 'request failed'}`,
        reason: 'request_failed',
      }
    }
  }

  return lastResult || {
    ok: false,
    label: source.label,
    url: source.url,
    reason: 'probe_failed_without_response',
  }
}

export default function InterviewRecordingPlayer({
  sessionToken,
  interviewId,
  asyncToken,
  recordingPath,
  recordingFormat,
  className,
  poster = '',
}) {
  const [, setIsInitializing] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [isRetryPending, setIsRetryPending] = useState(false)
  const [availabilityStatus, setAvailabilityStatus] = useState('idle')
  const [activeUrlIndex, setActiveUrlIndex] = useState(0)
  const [diagnosticMessage, setDiagnosticMessage] = useState('')
  const loadTimeoutRef = useRef(null)
  const retryTimeoutRef = useRef(null)
  const validationAbortRef = useRef(null)

  const candidateUrls = useMemo(
    () => buildRecordingUrls({ sessionToken, interviewId, asyncToken, recordingPath }),
    [asyncToken, interviewId, recordingPath, sessionToken]
  )
  const activeSource = candidateUrls[activeUrlIndex] || null
  const videoUrl = activeSource?.url || ''
  const authToken = useMemo(() => api.getToken(), [])
  const sources = useMemo(
    () => buildAuthorizedRecordingSources(videoUrl, recordingPath, recordingFormat, authToken),
    [authToken, recordingFormat, recordingPath, videoUrl]
  )
  const hasRecording = Boolean(videoUrl)
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
      setDiagnosticMessage('')
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
    setDiagnosticMessage('')
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

    probeRecordingSource(activeSource, authToken, abortController.signal)
      .then((probeResult) => {
        console.info('Interview recording probe:', {
          recordingPath,
          recordingFormat,
          sessionToken,
          asyncToken,
          interviewId,
          candidateSources: candidateUrls,
          activeSource,
          probeResult,
        })

        if (probeResult?.ok) {
          setAvailabilityStatus('available')
          setDiagnosticMessage(
            `${probeResult.label}: ${probeResult.status} ${probeResult.contentType || 'unknown-content-type'}`
          )
          return
        }

        const nextExists = tryNextSource()
        if (nextExists) {
          return
        }

        setAvailabilityStatus('invalid')
        setIsInitializing(false)
        setErrorMessage('Invalid video response from server')
        setDiagnosticMessage(summarizeProbeResult(probeResult))
      })
      .catch((error) => {
        if (error?.name === 'AbortError') {
          return
        }

        console.info('Interview recording probe failed:', {
          recordingPath,
          recordingFormat,
          sessionToken,
          asyncToken,
          interviewId,
          videoUrl,
          errorMessage: error?.message,
          errorName: error?.name,
        })

        if (tryNextSource()) {
          return
        }

        setAvailabilityStatus('invalid')
        setIsInitializing(false)
        setErrorMessage('Unable to load interview recording')
        setDiagnosticMessage(`${activeSource?.label || 'recording_source'}: ${error?.message || 'probe failed'}`)
      })

    loadTimeoutRef.current = setTimeout(() => {
      if (tryNextSource()) {
        return
      }
      setIsInitializing(false)
      setErrorMessage('Recording load timeout')
      setDiagnosticMessage(
        activeSource
          ? `${activeSource.label}: no playable response within ${LOAD_TIMEOUT_MS / 1000}s`
          : `No playable response within ${LOAD_TIMEOUT_MS / 1000}s`
      )
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
    setDiagnosticMessage(activeSource ? `${activeSource.label}: player ready` : '')
  }

  const handlePlayerError = (player) => {
    const playerError = player?.error?.()

    if (playerError?.code === 4 && tryNextSource()) {
      return
    }

    clearLoadTimeout()
    setIsInitializing(false)
    setErrorMessage(getPlayerErrorMessage(playerError))
    setDiagnosticMessage(
      activeSource
        ? `${activeSource.label}: Video.js code ${playerError?.code || 'unknown'} on ${videoUrl}`
        : `Video.js code ${playerError?.code || 'unknown'}`
    )

    console.error('Video playback error:', {
      recordingPath,
      recordingFormat,
      sessionToken,
      asyncToken,
      interviewId,
      videoUrl,
      activeSource,
      candidateSources: candidateUrls,
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
    setDiagnosticMessage('')
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
    <div className={cn('video-tab-container', className)}>
      <div className="video-wrapper">
        <div className="interview-recording-player-shell relative aspect-video w-full overflow-hidden rounded-[1.5rem] border border-slate-800/80 bg-black">
          {shouldRenderPlayer && !errorMessage ? (
            <VideoPlayer
              key={`${videoUrl}-${retryKey}`}
              sources={sources}
              poster={poster}
              preload="metadata"
              playsInline
              className="h-full w-full rounded-[1.5rem] bg-black"
              videoClassName="video-js vjs-default-skin custom-video object-cover object-center bg-black"
              /*options={{
                controls: true,
                fluid: true,
                responsive: true,
                inactivityTimeout: 0,
                playbackRates: [0.75, 1, 1.25, 1.5, 2],
                userActions: {
                  click: true,
                  hotkeys: true,
                },
                controlBar: {
                  playToggle: true,
                  currentTimeDisplay: true,
                  timeDivider: true,
                  durationDisplay: true,
                  progressControl: true,
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
                  playbackRateMenuButton: true,
                  fullscreenToggle: true,
                  pictureInPictureToggle: true,
                },
              }}*/
              options={{
                controls: true,

                fluid: false,
                responsive: false,
                fill: true,

                inactivityTimeout: 0,
                playbackRates: [0.75, 1, 1.25, 1.5, 2],
                userActions: {
                  click: true,
                  hotkeys: true,
                },
                controlBar: {
                  playToggle: true,
                  currentTimeDisplay: true,
                  timeDivider: true,
                  durationDisplay: true,
                  progressControl: true,
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
               playbackRateMenuButton: true,
               fullscreenToggle: true,
               pictureInPictureToggle: true,
              },
          }} 
              onLoadedData={handlePlayerReady}
              onCanPlay={handlePlayerReady}
              onError={handlePlayerError}
            />
          ) : null}

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
                {diagnosticMessage ? (
                  <p className="mt-2 text-xs text-white/50">
                    Debug: {diagnosticMessage}
                  </p>
                ) : null}
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
      </div>
    </div>
  )
}
