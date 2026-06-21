import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  ensureImportByPrivateId,
  getCsrfToken,
  getImportStatus,
  retryPartsetPipeline,
} from '../lib/api'
import { pipelineErrorMessage, LOCK_BUSY_MESSAGE, POLLING_FAILED_MESSAGE } from '../lib/pipelineErrors'
import { TransitionError, TransitionErrorButton } from '../components/TransitionError'

export function ImportProgressPage() {
  const { privateId } = useParams<{ privateId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [progress, setProgress] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [errorStage, setErrorStage] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const pollRef = useRef<(() => void) | null>(null)
  const previewError = import.meta.env.DEV ? searchParams.get('previewError') : null
  const canRetry = errorStage !== 'import_size'

  useEffect(() => {
    if (previewError) {
      setErrorStage(previewError)
      setErrorMessage(pipelineErrorMessage(previewError))
      return
    }

    if (!privateId) return

    let cancelled = false
    let timeoutId: number
    let failedAttempts = 0

    void ensureImportByPrivateId(privateId).catch(() => {
      // Polling will surface errors; ensure is best-effort on entry.
    })

    const poll = async () => {
      try {
        const data = await getImportStatus(privateId)
        if (cancelled) return

        if (data.error) {
          setErrorStage(data.error)
          setErrorMessage(pipelineErrorMessage(data.error, data.error_message))
          return
        }

        setErrorStage(null)
        setProgress(data.total_progress)
        failedAttempts = 0

        if (data.is_complete) {
          navigate(`/${privateId}/segment`)
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
  }, [privateId, navigate, previewError])

  const handleRetry = async () => {
    if (previewError) return
    if (!privateId || retrying) return

    if (errorMessage === POLLING_FAILED_MESSAGE) {
      setErrorMessage(null)
      setErrorStage(null)
      pollRef.current?.()
      return
    }

    setRetrying(true)
    try {
      const csrf = await getCsrfToken()
      const result = await retryPartsetPipeline(privateId, csrf)
      if (result.job_id === null) {
        setErrorMessage(LOCK_BUSY_MESSAGE)
        return
      }
      setErrorMessage(null)
      setErrorStage(null)
      setProgress(0)
      pollRef.current?.()
    } catch {
      setErrorMessage('Could not restart import. Please try again.')
    } finally {
      setRetrying(false)
    }
  }

  const ribbonWidth = progress * 4 + 20

  if (errorMessage) {
    return (
      <TransitionError message={errorMessage}>
        {canRetry ? (
          <TransitionErrorButton
            label={retrying ? 'Retrying…' : 'Try again'}
            onClick={handleRetry}
            disabled={retrying}
          />
        ) : null}
      </TransitionError>
    )
  }

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
