import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { PartsDownloadPane } from '../components/parts/PartsDownloadPane'
import { getCsrfToken, getPartsByAccessId, startPartGeneration } from '../lib/api'
import type { PartsDataResponse } from '../types/preview'

export function PartsPage() {
  const { privateId, accessId } = useParams<{ privateId?: string; accessId?: string }>()
  const id = privateId ?? accessId
  const navigate = useNavigate()
  const [data, setData] = useState<PartsDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    let cancelled = false
    ;(async () => {
      try {
        const parts = await getPartsByAccessId(id)
        if (cancelled) return
        if (!parts.parts_ready) {
          if (parts.mode === 'owner' && parts.private_id) {
            try {
              const csrf = await getCsrfToken()
              await startPartGeneration(parts.private_id, csrf)
            } catch {
              /* job may already be running */
            }
            navigate(`/${parts.private_id}/partgen`)
            return
          }
          setError('Parts are not ready for download yet.')
          return
        }
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
  }, [id, navigate])

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
