import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { SegmentEditor } from '../components/segment/SegmentEditor'
import { TransitionError } from '../components/TransitionError'
import { TransitionWait } from '../components/TransitionWait'
import { getSegmentData } from '../lib/api'
import { useNoIndex } from '../lib/useNoIndex'
import type { SegmentDataResponse } from '../types/segment'

const IMAGE_POLL_MS = 2000
const IMAGE_POLL_MAX = 300

export function SegmentPage() {
  useNoIndex()
  const { privateId } = useParams<{ privateId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<SegmentDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [warming, setWarming] = useState(false)
  const [warmProgress, setWarmProgress] = useState(0)

  useEffect(() => {
    if (!privateId) return
    let cancelled = false
    let timeoutId: number
    let pollCount = 0

    const poll = async () => {
      try {
        const payload = await getSegmentData(privateId)
        if (cancelled) return

        setData(payload)
        setLoading(false)
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
      }
    }

    poll()

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [privateId, navigate])

  return (
    <Layout>
      {loading ? (
        <div id="main" style={{ padding: '40px', textAlign: 'center' }}>
          Loading segment editor…
        </div>
      ) : warming ? (
        <TransitionWait
          message="Please wait while we prepare the score"
          progress={warmProgress}
        />
      ) : error ? (
        <TransitionError message={error} />
      ) : data ? (
        <SegmentEditor data={data} />
      ) : null}
    </Layout>
  )
}
