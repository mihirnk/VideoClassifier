import React, { forwardRef, useEffect } from 'react'

const VideoPlayer = forwardRef(({ src, onLoadedMetadata }, ref) => {
  useEffect(() => {
    if (!ref || !ref.current) return
    const el = ref.current
    const handler = () => onLoadedMetadata && onLoadedMetadata(el.duration)
    el.addEventListener('loadedmetadata', handler)
    return () => el.removeEventListener('loadedmetadata', handler)
  }, [ref, onLoadedMetadata, src])

  return (
    <div className="video-wrapper">
      {src ? (
        <video ref={ref} src={src} controls className="video-player" />
      ) : (
        <div className="video-placeholder">Select a local file to preview (or provide server path)</div>
      )}
    </div>
  )
})

export default VideoPlayer
