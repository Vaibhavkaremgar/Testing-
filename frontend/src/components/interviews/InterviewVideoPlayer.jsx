import { useEffect, useMemo, useRef } from 'react'
import videojs from 'video.js'
import 'video.js/dist/video-js.css'

import { cn } from '@/lib/utils'

function inferVideoType(videoUrl = '') {
  const normalizedUrl = String(videoUrl).split('?')[0].split('#')[0].toLowerCase()

  if (normalizedUrl.endsWith('.webm')) {
    return 'video/webm'
  }

  return 'video/mp4'
}

export default function InterviewVideoPlayer({
  videoUrl,
  className,
  videoClassName,
  poster = '',
}) {
  const videoElementRef = useRef(null)
  const playerRef = useRef(null)

  const source = useMemo(() => {
    const normalizedUrl = String(videoUrl || '').trim()
    if (!normalizedUrl) {
      return null
    }

    return {
      src: normalizedUrl,
      type: inferVideoType(normalizedUrl),
    }
  }, [videoUrl])

  useEffect(() => {
    if (!videoElementRef.current || playerRef.current) {
      return undefined
    }

    const player = videojs(videoElementRef.current, {
      controls: true,
      responsive: true,
      fluid: true,
      preload: 'metadata',
      playsinline: true,
      playbackRates: [0.5, 1, 1.5, 2],
      controlBar: {
        pictureInPictureToggle: false,
      },
      sources: source ? [source] : [],
    })

    if (poster) {
      player.poster(poster)
    }

    playerRef.current = player

    return () => {
      if (playerRef.current && !playerRef.current.isDisposed()) {
        playerRef.current.dispose()
        playerRef.current = null
      }
    }
  }, [poster, source])

  useEffect(() => {
    const player = playerRef.current
    if (!player) {
      return
    }

    if (poster) {
      player.poster(poster)
    }

    if (!source) {
      player.pause()
      player.reset()
      return
    }

    const [currentSource] = player.currentSources()
    if (currentSource?.src === source.src && currentSource?.type === source.type) {
      return
    }

    player.src(source)
    player.load()
  }, [poster, source])

  return (
    <div
      data-vjs-player
      className={cn(
        'h-full w-full overflow-hidden rounded-xl [&_.video-js]:h-full [&_.video-js]:w-full [&_.video-js]:overflow-hidden [&_.video-js]:rounded-xl',
        className
      )}
    >
      <video
        ref={videoElementRef}
        className={cn('video-js vjs-big-play-centered', videoClassName)}
      />
    </div>
  )
}
