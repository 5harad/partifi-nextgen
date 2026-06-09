import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { getPartsData } from '../lib/api'
import type { PartsDataResponse } from '../types/preview'

export function PartsPage() {
  const { privateId } = useParams<{ privateId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<PartsDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!privateId) return
    let cancelled = false
    ;(async () => {
      try {
        const parts = await getPartsData(privateId)
        if (cancelled) return
        if (!parts.parts_ready) {
          navigate(`/${privateId}/partgen`)
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
  }, [privateId, navigate])

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
        <div className="download-pane">
          <div className="box-top" />
          <div className="download-menu">
            <Link to={`/${privateId}/segment`} className="red">
              edit parts
            </Link>
          </div>
          <div className="partset-info">
            <div className="score-title">{data.title}</div>
            <div style={{ height: 5 }} />
            <div className="score-composer">{data.composer}</div>
            <div style={{ height: 5 }} />
            <div className="score-publisher">{data.publisher}</div>
          </div>
          <div className="partset-download">
            <div className="download-title">Download</div>
            {data.score_pdf_url && (
              <>
                <a
                  href={data.score_pdf_url}
                  className="red"
                  download={`${data.partset_id}_score.pdf`}
                >
                  complete score
                </a>
                <br />
              </>
            )}
            {data.parts.map((part) => (
              <span key={part.tag}>
                {part.tag}:{' '}
                <a
                  className="red"
                  href={part.letter_url}
                  download={`${data.partset_id}_${part.file_name}`}
                >
                  letter size
                </a>{' '}
                /{' '}
                <a
                  className="red"
                  href={part.a4_url}
                  download={`${data.partset_id}_a4_${part.file_name}`}
                >
                  a4
                </a>
                <br />
              </span>
            ))}
          </div>
          <div className="partset-links">
            <div className="partset-link">
              <div className="partset-link-label">editor link</div>
              <div className="partset-link-link">
                <Link className="red" to={`/${privateId}/preview`}>
                  {window.location.origin}/{privateId}/preview
                </Link>
              </div>
            </div>
          </div>
          <div className="box-bottom" />
        </div>
      </div>
    </Layout>
  )
}
