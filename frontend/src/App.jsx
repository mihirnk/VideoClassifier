import React, { useEffect, useRef, useState } from 'react'
import './index.css'
import VideoPlayer from './components/VideoPlayer'
import Timeline from './components/Timeline'
import SegmentList from './components/SegmentList'

function App() {
  const [localFile, setLocalFile] = useState(null)
  const [localURL, setLocalURL] = useState(null)

  // The backend expects a `video_path` (server-side path). Let user provide it.
  const [serverPath, setServerPath] = useState('videos/Mihir_clip.MOV')

  const [segments, setSegments] = useState([])
  const [duration, setDuration] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(null)

  const videoRef = useRef(null)

  useEffect(() => {
    if (!localFile) return
    const u = URL.createObjectURL(localFile)
    setLocalURL(u)
    return () => URL.revokeObjectURL(u)
  }, [localFile])

  async function handleAnalyze() {
    setError(null)
    setSegments([])
    setDuration(0)

    if (!serverPath) {
      setError('Please provide a server-side video path (e.g. videos/Mihir_clip.MOV)')
      return
    }

    setLoading(true)
    try {
      const res = await fetch('/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_path: serverPath })
      })
      if (!res.ok) {
        const txt = await res.text()
        throw new Error(`Server error: ${res.status} ${txt}`)
      }
      const data = await res.json()
      setSegments(data.segments || [])
      setDuration(data.duration || 0)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  function handleUpload() {
    setError(null)
    setSegments([])
    setDuration(0)

    if (!localFile) {
      setError('No local file selected to upload')
      return
    }

    setLoading(true)
    setUploadProgress(0)

    const form = new FormData()
    form.append('video', localFile)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/upload')
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setUploadProgress(Math.round((e.loaded / e.total) * 100))
      }
    }
    xhr.onreadystatechange = () => {
      if (xhr.readyState === 4) {
        setLoading(false)
        setUploadProgress(null)
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText)
            setSegments(data.segments || [])
            setDuration(data.duration || 0)
          } catch {
            setError('Failed to parse server response')
          }
        } else {
          setError(`Upload failed: ${xhr.status} ${xhr.statusText}`)
        }
      }
    }
    xhr.onerror = () => {
      setLoading(false)
      setUploadProgress(null)
      setError('Network error during upload')
    }
    xhr.send(form)
  }

  function handleLocalFile(e) {
    const f = e.target.files && e.target.files[0]
    if (f) setLocalFile(f)
  }

  function handleSeek(t) {
    if (videoRef.current) videoRef.current.currentTime = t
  }

  return (
    <div className="app-container">
      <header>
        <h1>Video Mode Annotator — Editor View</h1>
        <p className="muted">Select a video to preview locally, or give a server path to analyze.</p>
      </header>

      <section className="controls">
        <label className="field">
          <div className="label">Preview local file</div>
          <input type="file" accept="video/*" onChange={handleLocalFile} />
        </label>

        <label className="field">
          <div className="label">Server path (for /analyze)</div>
          <input type="text" value={serverPath} onChange={e => setServerPath(e.target.value)} placeholder="videos/your_file.MP4" />
        </label>

        <div className="actions">
          <button onClick={handleAnalyze} disabled={loading} className="btn primary">{loading ? 'Analyzing…' : 'Analyze'}</button>
          <button onClick={handleUpload} disabled={loading} className="btn" style={{ marginLeft: 8 }}>{loading ? 'Uploading…' : 'Upload'}</button>
        </div>
        {uploadProgress !== null && (
          <div className="upload-progress">Uploading: {uploadProgress}%</div>
        )}
        {error && <div className="error">{error}</div>}
      </section>

      <main className="main-grid">
        <div className="player-column">
          <VideoPlayer ref={videoRef} src={localURL} onLoadedMetadata={(d) => setDuration(d)} />
          <Timeline segments={segments} duration={duration} videoRef={videoRef} onSeek={handleSeek} />
        </div>

        <aside className="sidebar">
          <h3>Segments</h3>
          <SegmentList segments={segments} onSeek={handleSeek} />
        </aside>
      </main>
    </div>
  )
}

export default App
