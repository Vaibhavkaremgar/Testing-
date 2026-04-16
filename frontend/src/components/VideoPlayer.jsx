import { forwardRef, useEffect, useMemo, useRef, useState } from 'react'
import videojs from 'video.js'
import 'video.js/dist/video-js.css'
import { cn } from '@/lib/utils'

function inferSourceType(src = '') {
  const normalizedSrc = src.split('?')[0].split('#')[0].toLowerCase()

  if (normalizedSrc.endsWith('.m3u8')) {
    return 'application/x-mpegURL'
  }

  return 'video/mp4'
}

function normalizeSources({ src, type, sources }) {
  if (Array.isArray(sources) && sources.length > 0) {
    return sources
      .filter((source) => source?.src)
      .map((source) => {
        const normalizedSource = { ...source, src: source.src }

        // Preserve an omitted type so the browser can rely on the backend
        // response Content-Type instead of a guessed MIME.
        if (Object.prototype.hasOwnProperty.call(source, 'type')) {
          normalizedSource.type = source.type
        }

        return normalizedSource
      })
  }

  if (!src) {
    return []
  }

  const normalizedSource = { src }
  if (type !== undefined) {
    normalizedSource.type = type
  } else if (src.includes('.m3u8')) {
    normalizedSource.type = inferSourceType(src)
  }

  return [normalizedSource]
}

const VideoPlayer = forwardRef(function VideoPlayer(
  {
    src = '',
    type,
    sources,
    options,
    className,
    videoClassName,
    poster = '',
    playsInline = true,
    preload = 'metadata',
    onReady,
    onError,
    onLoadedMetadata,
    onLoadedData,
    onCanPlay,
    onDurationChange,
    onTimeUpdate,
    onPlay,
    onPause,
    onEnded,
  },
  ref
) {
  const videoElementRef = useRef(null)
  const playerRef = useRef(null)
  const optionsRef = useRef(options)
  const speedMenuControlRef = useRef(null)
  const speedMenuRef = useRef(null)
  const [isSpeedMenuOpen, setIsSpeedMenuOpen] = useState(false)
  const normalizedSources = useMemo(
    () => normalizeSources({ src, type, sources }),
    [src, type, sources]
  )

  useEffect(() => {
    if (!videoElementRef.current || playerRef.current) {
      return undefined
    }

    const player = videojs(videoElementRef.current, {
      controls: true,
      responsive: false,
      fluid: false,
      preload,
      playsinline: playsInline,
      sources: normalizedSources,
      ...optionsRef.current,
    })

    playerRef.current = player
    if (ref) {
      if (typeof ref === 'function') {
        ref(player)
      } else {
        ref.current = player
      }
    }

    if (poster) {
      player.poster(poster)
    }

    if (onReady) {
      player.ready(() => onReady(player))
    }

    return () => {
      if (playerRef.current && !playerRef.current.isDisposed()) {
        playerRef.current.dispose()
        playerRef.current = null
      }

      if (ref) {
        if (typeof ref === 'function') {
          ref(null)
        } else {
          ref.current = null
        }
      }
    }
  }, [onReady, playsInline, poster, preload, ref])

  useEffect(() => {
    const player = playerRef.current

    if (!player) {
      return
    }

    if (poster) {
      player.poster(poster)
    }

    if (normalizedSources.length === 0) {
      player.pause()
      player.reset()
      return
    }

    const [nextSource] = normalizedSources
    const currentSources = Array.isArray(player.currentSources?.())
      ? player.currentSources()
      : []
    const [currentSource] = currentSources

    if (currentSource?.src === nextSource.src && currentSource?.type === nextSource.type) {
      return
    }

    player.src(normalizedSources.length === 1 ? normalizedSources[0] : normalizedSources)
    player.load()
  }, [normalizedSources, poster])

  useEffect(() => {
    const player = playerRef.current

    if (!player) {
      return undefined
    }

    const listeners = [
      ['error', onError],
      ['loadedmetadata', onLoadedMetadata],
      ['loadeddata', onLoadedData],
      ['canplay', onCanPlay],
      ['durationchange', onDurationChange],
      ['timeupdate', onTimeUpdate],
      ['play', onPlay],
      ['pause', onPause],
      ['ended', onEnded],
    ]
      .filter(([, handler]) => typeof handler === 'function')
      .map(([eventName, handler]) => {
        const listener = () => handler(player)
        player.on(eventName, listener)
        return [eventName, listener]
      })

    return () => {
      listeners.forEach(([eventName, listener]) => {
        player.off(eventName, listener)
      })
    }
  }, [
    onCanPlay,
    onDurationChange,
    onEnded,
    onError,
    onLoadedData,
    onLoadedMetadata,
    onPause,
    onPlay,
    onTimeUpdate,
  ])

  useEffect(() => {
    const player = playerRef.current
    const playerElement = player?.el?.()

    if (!player || !playerElement) {
      return undefined
    }

    const playbackRateControl = playerElement.querySelector('.vjs-playback-rate')
    const playbackRateMenu = playbackRateControl?.querySelector('.vjs-menu')

    if (!playbackRateControl || !playbackRateMenu) {
      return undefined
    }

    speedMenuControlRef.current = playbackRateControl
    speedMenuRef.current = playbackRateMenu

    const handleToggleMenu = (event) => {
      event.preventDefault()
      event.stopPropagation()
      player.userActive(true)
      setIsSpeedMenuOpen((prev) => !prev)
    }

    const handleMenuMouseDown = (event) => {
      event.stopPropagation()
    }

    const handleMenuClick = (event) => {
      event.stopPropagation()
      player.userActive(true)

      if (event.target.closest('.vjs-menu-item')) {
        window.setTimeout(() => setIsSpeedMenuOpen(false), 0)
        return
      }
    }

    const handleWindowClick = (event) => {
      if (playbackRateControl.contains(event.target)) {
        return
      }
      setIsSpeedMenuOpen(false)
    }

    playbackRateControl.addEventListener('click', handleToggleMenu)
    playbackRateMenu.addEventListener('mousedown', handleMenuMouseDown)
    playbackRateMenu.addEventListener('click', handleMenuClick)
    window.addEventListener('click', handleWindowClick)

    return () => {
      playbackRateControl.removeEventListener('click', handleToggleMenu)
      playbackRateMenu.removeEventListener('mousedown', handleMenuMouseDown)
      playbackRateMenu.removeEventListener('click', handleMenuClick)
      window.removeEventListener('click', handleWindowClick)
      speedMenuControlRef.current = null
      speedMenuRef.current = null
    }
  }, [])

  useEffect(() => {
    const player = playerRef.current
    const playbackRateControl = speedMenuControlRef.current

    if (!player || !playbackRateControl) {
      return
    }

    player.userActive(true)
    playbackRateControl.classList.toggle('vjs-menu-button-active', isSpeedMenuOpen)
    playbackRateControl.classList.toggle('vjs-lock-showing', isSpeedMenuOpen)
  }, [isSpeedMenuOpen])

  return (
    <div
      data-vjs-player
      className={cn(
        'h-full w-full overflow-visible rounded-lg [&_.video-js]:h-full [&_.video-js]:w-full [&_.video-js]:overflow-visible [&_.video-js]:rounded-lg [&_.vjs-big-play-button]:bg-transparent [&_.vjs-big-play-button]:border-transparent [&_.vjs-big-play-button:hover]:bg-transparent [&_.vjs-big-play-button:hover]:border-transparent [&_.vjs-big-play-button:focus]:bg-transparent [&_.vjs-big-play-button:focus]:border-transparent',
        className
      )}
    >
      <video
        ref={videoElementRef}
        className={cn('video-js vjs-big-play-centered', videoClassName)}
      />
    </div>
  )
})

export default VideoPlayer
