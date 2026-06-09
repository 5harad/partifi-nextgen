import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getImportStatus } from '../lib/api'

export function ImportProgressPage() {
  const { privateId } = useParams<{ privateId: string }>()
  const navigate = useNavigate()
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    if (!privateId) return

    let cancelled = false
    let timeoutId: number
    let failedAttempts = 0

    const poll = async () => {
      try {
        const data = await getImportStatus(privateId)
        if (cancelled) return

        if (data.error) {
          navigate(`/?err=${data.error}`)
          return
        }

        setProgress(data.total_progress)
        failedAttempts = 0

        if (data.is_complete) {
          navigate(`/${privateId}/segment`)
          return
        }
      } catch {
        failedAttempts += 1
      }

      if (!cancelled && failedAttempts < 20) {
        timeoutId = window.setTimeout(poll, 500)
      }
    }

    poll()

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [privateId, navigate])

  const ribbonWidth = progress * 4 + 20

  return (
    <div id="main" style={{ height: '750px' }}>
      <img
        src="/images/notes_bg.jpg"
        width={1190}
        height={252}
        style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
        alt=""
      />
      <div id="transition">
        <div id="transition-text">Please wait while we import the score</div>
        <div id="progress-bar">
          <div id="progress-ribbon" style={{ width: ribbonWidth }} />
        </div>
      </div>
    </div>
  )
}
