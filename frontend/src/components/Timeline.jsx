import React, { useEffect, useRef, useState } from 'react'

function colorForMode(mode) {
  switch (mode) {
    case 'DIALOGUE_SCENE':
      return '#4f46e5' // indigo
    case 'VISUAL_MONTAGE':
      return '#ef4444' // red
    case 'VOICEOVER_WITH_PICTURE':
      return '#10b981' // green
    default:
      return '#94a3b8'
  }
}

export default function Timeline({ segments = [], duration = 0, videoRef, onSeek }) {
  const containerRef = useRef(null)
  const [playhead, setPlayhead] = useState(0)

  useEffect(() => {
    let raf = null
    function tick() {
      if (videoRef && videoRef.current && duration > 0) {
        setPlayhead(videoRef.current.currentTime / duration)
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [videoRef, duration])

  function pct(t) {
    if (!duration || duration <= 0) return 0
    return Math.max(0, Math.min(100, (t / duration) * 100))
  }

  function handleClick(e) {
    if (!containerRef.current || !onSeek) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const p = x / rect.width
    onSeek(p * duration)
  }

  return (
    <div className="timeline-container">
      <div className="timeline" ref={containerRef} onClick={handleClick}>
        {segments.map((s, i) => (
          <div
            key={i}
            className="segment"
            title={`${s.mode} ${s.start.toFixed(2)}–${s.end.toFixed(2)}`}
            style={{
              left: `${pct(s.start)}%`,
              width: `${Math.max(0.2, pct(s.end) - pct(s.start))}%`,
              background: colorForMode(s.mode)
            }}
          />
        ))}

        <div className="playhead" style={{ left: `${playhead * 100}%` }} />
      </div>
      <div className="timeline-legend">
        <span><span className="legend-box" style={{ background: colorForMode('DIALOGUE_SCENE') }} />DIALOGUE_SCENE</span>
        <span><span className="legend-box" style={{ background: colorForMode('VISUAL_MONTAGE') }} />VISUAL_MONTAGE</span>
        <span><span className="legend-box" style={{ background: colorForMode('VOICEOVER_WITH_PICTURE') }} />VOICEOVER_WITH_PICTURE</span>
      </div>
    </div>
  )
}
