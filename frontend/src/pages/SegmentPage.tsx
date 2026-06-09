import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { SegmentEditor } from '../components/segment/SegmentEditor'
import { getSegmentData } from '../lib/api'
import type { SegmentDataResponse } from '../types/segment'

export function SegmentPage() {
  const { privateId } = useParams<{ privateId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<SegmentDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!privateId) return
    let cancelled = false

    getSegmentData(privateId)
      .then((payload) => {
        if (!cancelled) setData(payload)
      })
      .catch((err: Error) => {
        if (!cancelled) {
          if (err.message.includes('Import not complete')) {
            navigate(`/${privateId}/import`)
            return
          }
          setError(err.message)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [privateId, navigate])

  return (
    <Layout>
      {loading ? (
        <div id="main" style={{ padding: '40px', textAlign: 'center' }}>
          Loading segment editor…
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
