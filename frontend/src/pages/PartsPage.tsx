import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { TransitionError } from '../components/TransitionError'
import { PartsDownloadPane } from '../components/parts/PartsDownloadPane'
import { getPartsByAccessId } from '../lib/api'
import { isPartsetAccessId } from '../lib/partsetRoutes'
import type { PartsDataResponse } from '../types/preview'

const PARTSET_NOT_FOUND_MESSAGE = 'Partset not found'

export function PartsPage() {
  const { accessId } = useParams<{ accessId: string }>()
  const [data, setData] = useState<PartsDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleDataChange = useCallback((update: React.SetStateAction<PartsDataResponse>) => {
    setData((prev) => {
      if (!prev) return prev
      return typeof update === 'function' ? update(prev) : update
    })
  }, [])

  useEffect(() => {
    if (!isPartsetAccessId(accessId)) {
      setError(PARTSET_NOT_FOUND_MESSAGE)
      setData(null)
      return
    }
    setError(null)
    let cancelled = false
    ;(async () => {
      try {
        const parts = await getPartsByAccessId(accessId)
        if (cancelled) return
        setData(parts)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load parts')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [accessId])

  if (error) {
    return (
      <Layout>
        <TransitionError message={error} />
      </Layout>
    )
  }

  if (!data) {
    return (
      <Layout>
        <div id="main" style={{ minHeight: '750px' }}>
          <div id="transition">
            <div id="transition-text">Loading…</div>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div id="main" className="parts-page">
        <img
          src="/images/notes_bg.jpg"
          width={1190}
          height={252}
          style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
          alt=""
        />
        <PartsDownloadPane data={data} onDataChange={handleDataChange} />
      </div>
    </Layout>
  )
}
