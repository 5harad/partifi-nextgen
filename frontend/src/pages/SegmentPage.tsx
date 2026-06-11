import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { SegmentEditor } from '../components/segment/SegmentEditor'
import { getSegmentData } from '../lib/api'
import type { SegmentDataResponse } from '../types/segment'

const IMAGE_POLL_MS = 2000
const IMAGE_POLL_MAX = 300

export function SegmentPage() {
  const { privateId } = useParams<{ privateId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<SegmentDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [warming, setWarming] = useState(false)

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

        if (!payload.images_ready) {
          pollCount += 1
          if (pollCount >= IMAGE_POLL_MAX) {
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
        <div id="main" style={{ padding: '40px', textAlign: 'center' }}>
          <div id="transition-text">Please wait while we prepare the score images</div>
          <div id="progress-bar">
            <div id="progress-ribbon" style={{ width: 120 }} />
          </div>
        </div>
      ) : error ? (
        <div id="main" style={{ padding: '40px', textAlign: 'center' }}>
          <p className="red">{error}</p>
        </div>
      ) : data ? (
        <SegmentEditor data={data} />
      ) : null}
    </Layout>
  )
}
