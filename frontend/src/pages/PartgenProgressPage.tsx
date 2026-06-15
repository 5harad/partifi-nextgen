import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  getCsrfToken,
  getPartgenStatusByAccessId,
  ensurePartsByAccessId,
  retryPartsetPipelineByAccessId,
} from '../lib/api'
import { triggerPartFileDownload } from '../lib/partDownloads'
import { pipelineErrorMessage, LOCK_BUSY_MESSAGE, POLLING_FAILED_MESSAGE } from '../lib/pipelineErrors'

export function PartgenProgressPage() {
  const { privateId: accessId } = useParams<{ privateId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [progress, setProgress] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const pollRef = useRef<(() => void) | null>(null)
  const previewError = import.meta.env.DEV ? searchParams.get('previewError') : null
  const pendingDownloadUrl = searchParams.get('download')

  useEffect(() => {
    if (previewError) {
      setErrorMessage(pipelineErrorMessage(previewError))
      return
    }

    if (!accessId) return

    let cancelled = false
    let timeoutId: number
    let failedAttempts = 0

    void ensurePartsByAccessId(accessId).catch(() => {
      // Polling will surface errors; ensure is best-effort on entry.
    })

    const poll = async () => {
      try {
        const data = await getPartgenStatusByAccessId(accessId)
        if (cancelled) return

        if (data.error) {
          setErrorMessage(pipelineErrorMessage(data.error))
          return
        }

        setProgress(data.total_progress)
        failedAttempts = 0

        if (data.is_complete) {
          if (pendingDownloadUrl) {
            void triggerPartFileDownload(pendingDownloadUrl).finally(() => {
              if (!cancelled) navigate(`/${accessId}`)
            })
          } else {
            navigate(`/${accessId}`)
          }
          return
        }
      } catch {
        failedAttempts += 1
        if (failedAttempts >= 20 && !cancelled) {
          setErrorMessage(POLLING_FAILED_MESSAGE)
          return
        }
      }

      if (!cancelled && failedAttempts < 20) {
        timeoutId = window.setTimeout(poll, 500)
      }
    }

    pollRef.current = () => {
      cancelled = false
      failedAttempts = 0
      window.clearTimeout(timeoutId)
      poll()
    }

    poll()

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [accessId, navigate, previewError, pendingDownloadUrl])

  const handleRetry = async () => {
    if (previewError) return
    if (!accessId || retrying) return

    if (errorMessage === POLLING_FAILED_MESSAGE) {
      setErrorMessage(null)
      pollRef.current?.()
      return
    }

    setRetrying(true)
    try {
      const csrf = await getCsrfToken()
      const result = await retryPartsetPipelineByAccessId(accessId, csrf)
      if (result.job_id === null) {
        setErrorMessage(LOCK_BUSY_MESSAGE)
        return
      }
      setErrorMessage(null)
      setProgress(0)
      pollRef.current?.()
    } catch {
      setErrorMessage('Could not restart part generation. Please try again.')
    } finally {
      setRetrying(false)
    }
  }

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
      <div id="transition" className={errorMessage ? 'transition-error' : undefined}>
        {errorMessage ? (
          <>
            <div id="transition-text">{errorMessage}</div>
            <div id="transition-actions">
              <div
                className={`copy-button${retrying ? ' is-disabled' : ''}`}
                onClick={retrying ? undefined : handleRetry}
                onKeyDown={() => {}}
                role="button"
                tabIndex={retrying ? -1 : 0}
              >
                {retrying ? 'Retrying…' : 'Try again'}
              </div>
              <div
                className="copy-button"
                onClick={() => accessId && navigate(`/${accessId}`)}
                onKeyDown={() => {}}
                role="button"
                tabIndex={0}
              >
                Back to download
              </div>
            </div>
          </>
        ) : (
          <>
            <div id="transition-text">Please wait while we partifi the score</div>
            <div id="progress-bar">
              <div id="progress-ribbon" style={{ width: ribbonWidth }} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
