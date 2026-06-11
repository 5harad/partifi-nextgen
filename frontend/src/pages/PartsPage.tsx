import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { PartsDownloadPane } from '../components/parts/PartsDownloadPane'
import { getPartsByAccessId } from '../lib/api'
import type { PartsDataResponse } from '../types/preview'

export function PartsPage() {
  const { accessId } = useParams<{ accessId: string }>()
  const [data, setData] = useState<PartsDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!accessId) return
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
        <div id="main" style={{ height: '750px', padding: '40px' }}>
          <p className="red">{error}</p>
        </div>
      </Layout>
    )
  }

  if (!data) {
    return (
      <Layout>
        <div id="main" style={{ height: '750px' }}>
          <div id="transition">
            <div id="transition-text">Loading…</div>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div id="main" style={{ height: '750px' }}>
        <img
          src="/images/notes_bg.jpg"
          width={1190}
          height={252}
          style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
          alt=""
        />
        <PartsDownloadPane data={data} onDataChange={setData} />
      </div>
    </Layout>
  )
}
