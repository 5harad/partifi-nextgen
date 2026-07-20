import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { SegmentEditor } from '../components/segment/SegmentEditor'
import { TransitionError, TransitionErrorButton } from '../components/TransitionError'
import { TransitionWait } from '../components/TransitionWait'
import { getCsrfToken, getSegmentData, retryPartsetPageCache } from '../lib/api'
import { LOCK_BUSY_MESSAGE } from '../lib/pipelineErrors'
import { useNoIndex } from '../lib/useNoIndex'
import type { SegmentDataResponse } from '../types/segment'

const IMAGE_POLL_MS = 2000
const IMAGE_POLL_MAX = 300
const LOADING_INDICATOR_DELAY_MS = 200

export function SegmentPage() {
  useNoIndex()
  const { privateId } = useParams<{ privateId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<SegmentDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showLoadingIndicator, setShowLoadingIndicator] = useState(false)
  const [warming, setWarming] = useState(false)
  const [warmProgress, setWarmProgress] = useState(0)
  const [cacheError, setCacheError] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const pollRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!privateId) return
    let cancelled = false
    let timeoutId: number
    const loadingIndicatorTimeout = window.setTimeout(() => {
      if (!cancelled) setShowLoadingIndicator(true)
    }, LOADING_INDICATOR_DELAY_MS)
    let pollCount = 0

    const poll = async () => {
      try {
        const payload = await getSegmentData(privateId)
        if (cancelled) return

        setData(payload)
        setLoading(false)
        setShowLoadingIndicator(false)
        window.clearTimeout(loadingIndicatorTimeout)

        if (payload.image_cache_error_message) {
          setCacheError(true)
          setWarming(false)
          setError(payload.image_cache_error_message)
          return
        }

        setCacheError(false)
        setError(null)
        setWarming(!payload.images_ready)
        setWarmProgress(payload.image_progress)

        if (!payload.images_ready) {
          pollCount += 1
          if (pollCount >= IMAGE_POLL_MAX) {
            setWarming(false)
            setError(
              'Score images are taking longer than expected. Please refresh the page in a few minutes.',
            )
            return
          }
          timeoutId = window.setTimeout(poll, IMAGE_POLL_MS)
        }
      } catch (err: unknown) {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Failed to load segment data'
        if (message.includes('Import not complete')) {
          navigate(`/${privateId}/import`)
          return
        }
        setError(message)
        setLoading(false)
        setShowLoadingIndicator(false)
        window.clearTimeout(loadingIndicatorTimeout)
      }
    }

    pollRef.current = () => {
      cancelled = false
      pollCount = 0
      window.clearTimeout(timeoutId)
      void poll()
    }

    void poll()

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
      window.clearTimeout(loadingIndicatorTimeout)
    }
  }, [privateId, navigate])

  const handleRetryPageCache = async () => {
    if (!privateId || retrying) return
    setRetrying(true)
    try {
      const token = await getCsrfToken()
      await retryPartsetPageCache(privateId, token)
      setError(null)
      setCacheError(false)
      setWarming(true)
      setWarmProgress(0)
      pollRef.current?.()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to retry page images'
      setError(message === 'Failed to fetch' ? LOCK_BUSY_MESSAGE : message)
    } finally {
      setRetrying(false)
    }
  }

  return (
    <Layout showChrome={!warming}>
      {loading && showLoadingIndicator ? (
        <div id="main" style={{ padding: '40px', textAlign: 'center' }}>
          Loading segment editor…
        </div>
      ) : warming ? (
        <TransitionWait
          message="Please wait while we prepare the score"
          progress={warmProgress}
        />
      ) : error ? (
        <TransitionError message={error}>
          {cacheError ? (
            <TransitionErrorButton
              label={retrying ? 'Retrying…' : 'Try again'}
              onClick={handleRetryPageCache}
              disabled={retrying}
            />
          ) : null}
        </TransitionError>
      ) : data ? (
        <SegmentEditor data={data} />
      ) : null}
    </Layout>
  )
}
