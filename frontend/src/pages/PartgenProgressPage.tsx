import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getCsrfToken, getPartgenStatus, startPartGeneration } from '../lib/api'

export function PartgenProgressPage() {
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
        const data = await getPartgenStatus(privateId)
        if (cancelled) return

        if (data.error) {
          navigate(`/?err=${data.error}`)
          return
        }

        setProgress(data.total_progress)
        failedAttempts = 0

        if (data.is_complete) {
          navigate(`/${privateId}/parts`)
          return
        }
      } catch {
        failedAttempts += 1
      }

      if (!cancelled && failedAttempts < 20) {
        timeoutId = window.setTimeout(poll, 500)
      }
    }

    ;(async () => {
      try {
        const csrf = await getCsrfToken()
        await startPartGeneration(privateId, csrf)
      } catch {
        /* job may already be running */
      }
      poll()
    })()

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
        <div id="transition-text">Please wait while we partifi the score</div>
        <div id="progress-bar">
          <div id="progress-ribbon" style={{ width: ribbonWidth }} />
        </div>
      </div>
    </div>
  )
}
