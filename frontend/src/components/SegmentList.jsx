import React from 'react'

export default function SegmentList({ segments = [], onSeek }) {
  function fmt(n) {
    return typeof n === 'number' ? n.toFixed(2) : n
  }

  return (
    <div className="segment-list">
      {segments.length === 0 && <div className="muted">No segments yet</div>}
      {segments.map((s, i) => (
        <div key={i} className="segment-row" onClick={() => onSeek && onSeek(s.start)}>
          <div className="seg-mode">{s.mode}</div>
          <div className="seg-times">{fmt(s.start)} — {fmt(s.end)}</div>
        </div>
      ))}
    </div>
  )
}
