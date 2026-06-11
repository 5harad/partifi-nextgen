import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { getCsrfToken, getPartgenStatus, retryPartsetPipeline } from '../lib/api'
import { pipelineErrorMessage, POLLING_FAILED_MESSAGE } from '../lib/pipelineErrors'

export function PartgenProgressPage() {
  const { privateId } = useParams<{ privateId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [progress, setProgress] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const pollRef = useRef<(() => void) | null>(null)
  const previewError = import.meta.env.DEV ? searchParams.get('previewError') : null

  useEffect(() => {
    if (previewError) {
      setErrorMessage(pipelineErrorMessage(previewError))
      return
    }

    if (!privateId) return

    let cancelled = false
    let timeoutId: number
    let failedAttempts = 0

    const poll = async () => {
      try {
        const data = await getPartgenStatus(privateId)
        if (cancelled) return

        if (data.error) {
          setErrorMessage(pipelineErrorMessage(data.error))
          return
        }

        setProgress(data.total_progress)
        failedAttempts = 0

        if (data.is_complete) {
          navigate(`/${privateId}`)
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
      pollRef.current?.()
      return
    }

    setRetrying(true)
    try {
      const csrf = await getCsrfToken()
      await retryPartsetPipeline(privateId, csrf)
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
                onClick={() => privateId && navigate(`/${privateId}/preview`)}
                onKeyDown={() => {}}
                role="button"
                tabIndex={0}
              >
                Back to preview
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
