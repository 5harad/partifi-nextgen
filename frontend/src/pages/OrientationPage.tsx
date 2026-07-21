import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { TransitionError, TransitionErrorButton } from '../components/TransitionError'
import { TransitionWait } from '../components/TransitionWait'
import { getCsrfToken, getOrientationData, reorientPartset, retryPartsetPipeline } from '../lib/api'
import { LOCK_BUSY_MESSAGE } from '../lib/pipelineErrors'
import { getDimensions } from '../lib/pageDimensions'
import { useNoIndex } from '../lib/useNoIndex'
import type { OrientationDataResponse, OrientationOption } from '../types/orientation'

const POLL_MS = 500
const ORIENTATION_PREVIEW_BASE_WIDTH = 220
const ORIENTATION_PANEL_INNER_WIDTH = 885 - 38
const ORIENTATION_OPTION_GAP = 14

type PreviewLayout = {
  options: Array<OrientationOption & { displayWidth: number; displayHeight: number }>
  rowScale: number
  rowHeight: number
}

function buildPreviewLayout(data: OrientationDataResponse): PreviewLayout {
  const dims = getDimensions(data.score_orientation)
  const scale = ORIENTATION_PREVIEW_BASE_WIDTH / dims.lowresWidth
  const options = data.rotation_options.map((option) => {
    const sideways = option.degrees === 90 || option.degrees === 270
    const nativeW = sideways ? dims.lowresHeight : dims.lowresWidth
    const nativeH = sideways ? dims.lowresWidth : dims.lowresHeight
    return {
      ...option,
      displayWidth: Math.round(nativeW * scale),
      displayHeight: Math.round(nativeH * scale),
    }
  })

  const total =
    options.reduce((sum, option) => sum + option.displayWidth, 0) +
    ORIENTATION_OPTION_GAP * (options.length - 1)
  const rowScale = total > ORIENTATION_PANEL_INNER_WIDTH ? ORIENTATION_PANEL_INNER_WIDTH / total : 1
  const rowHeight = Math.max(...options.map((option) => option.displayHeight))

  return { options, rowScale, rowHeight }
}

export function OrientationPage() {
  useNoIndex()
  const { privateId } = useParams<{ privateId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<OrientationDataResponse | null>(null)
  const [selectedDegrees, setSelectedDegrees] = useState(0)
  const [splitTwoUpDegrees, setSplitTwoUpDegrees] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const wasReimportingRef = useRef(false)
  const sawReimportInProgressRef = useRef(false)
  const pollRef = useRef<(() => void) | null>(null)

  const loadData = useCallback(async () => {
    if (!privateId) return null
    return getOrientationData(privateId)
  }, [privateId])

  useEffect(() => {
    if (!privateId) return
    let cancelled = false
    let timeoutId: number

    const poll = async () => {
      try {
        const payload = await loadData()
        if (cancelled || !payload) return
        setData(payload)
        if (!payload.reimport_in_progress && !wasReimportingRef.current) {
          setSelectedDegrees(payload.current_rotation_degrees)
          setSplitTwoUpDegrees(
            payload.current_split_two_up ? payload.current_rotation_degrees : null,
          )
        }
        setLoading(false)
        setError(null)

        if (payload.reimport_in_progress) {
          wasReimportingRef.current = true
          sawReimportInProgressRef.current = true
        }

        if (payload.reimport_error) {
          setError(payload.reimport_error_message || 'Reorient failed')
          return
        }

        if (payload.reimport_in_progress) {
          timeoutId = window.setTimeout(poll, POLL_MS)
        }
      } catch (err: unknown) {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Failed to load orientation data'
        if (message.includes('Import not complete') && wasReimportingRef.current) {
          timeoutId = window.setTimeout(poll, POLL_MS)
          return
        }
        if (message.includes('Import not complete')) {
          navigate(`/${privateId}/import`)
          return
        }
        setError(message)
        setLoading(false)
      }
    }

    pollRef.current = () => {
      cancelled = false
      window.clearTimeout(timeoutId)
      void poll()
    }

    void poll()

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [privateId, loadData, navigate])

  useEffect(() => {
    if (
      sawReimportInProgressRef.current &&
      data &&
      !data.reimport_in_progress &&
      !data.reimport_error &&
      data.reimport_progress >= 100
    ) {
      navigate(`/${privateId}/segment`)
    }
  }, [data, navigate, privateId])

  const handleRetry = async () => {
    if (!privateId || retrying) return
    setRetrying(true)
    try {
      const token = await getCsrfToken()
      const result = await retryPartsetPipeline(privateId, token)
      if (result.job_id === null) {
        setError(LOCK_BUSY_MESSAGE)
        return
      }
      setError(null)
      wasReimportingRef.current = true
      sawReimportInProgressRef.current = true
      setLoading(false)
      setData((prev) =>
        prev
          ? {
              ...prev,
              reimport_in_progress: true,
              reimport_progress: 33,
              reimport_error: null,
              reimport_error_message: null,
            }
          : prev,
      )
      pollRef.current?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reorient failed')
    } finally {
      setRetrying(false)
    }
  }

  const handleReimport = async () => {
    if (!privateId || submitting) return
    try {
      setSubmitting(true)
      setError(null)
      const token = await getCsrfToken()
      await reorientPartset(
        privateId,
        selectedDegrees,
        splitTwoUpDegrees === selectedDegrees,
        token,
      )
      wasReimportingRef.current = true
      sawReimportInProgressRef.current = true
      setLoading(false)
      setData((prev) =>
        prev
          ? { ...prev, reimport_in_progress: true, reimport_progress: 33, reimport_error: null }
          : prev,
      )
      pollRef.current?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reorient failed')
    } finally {
      setSubmitting(false)
    }
  }

  const reimporting = Boolean(data?.reimport_in_progress)
  const previewLayout = useMemo(() => (data ? buildPreviewLayout(data) : null), [data])

  return (
    <Layout showChrome={!reimporting}>
      {loading ? (
        <div id="main" style={{ padding: '40px', textAlign: 'center' }}>
          Loading orientation options…
        </div>
      ) : reimporting ? (
        <TransitionWait
          message="Reorienting the score"
          progress={data?.reimport_progress ?? 0}
        />
      ) : error ? (
        <TransitionError message={error}>
          <TransitionErrorButton
            label={retrying ? 'Retrying…' : 'Try again'}
            onClick={handleRetry}
            disabled={retrying}
          />
        </TransitionError>
      ) : data ? (
        <div id="main">
          <img
            src="/images/notes_bg.jpg"
            width={1190}
            height={252}
            style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
            alt=""
          />
          <div id="segment-header">Fix page orientation</div>
          <div
            id="orientation-panel"
            style={
              previewLayout
                ? ({ '--orientation-row-scale': previewLayout.rowScale } as React.CSSProperties)
                : undefined
            }
          >
            <div className="orientation-intro">
              <p>
                Select the correct orientation. Beware that reorienting the score will erase any
                existing segments and parts!
              </p>
            </div>
            <div className="orientation-options-wrap">
              <div className="orientation-options">
                {previewLayout?.options.map((option) => {
                  const selected = option.degrees === selectedDegrees
                  const width = Math.round(option.displayWidth * (previewLayout?.rowScale ?? 1))
                  const height = Math.round(option.displayHeight * (previewLayout?.rowScale ?? 1))
                  const splitSelected = splitTwoUpDegrees === option.degrees
                  return (
                    <div key={option.degrees}>
                      <button
                        type="button"
                        className={`orientation-option${selected ? ' orientation-option-selected' : ''}`}
                        onClick={() => setSelectedDegrees(option.degrees)}
                        aria-label={`Rotate ${option.degrees} degrees`}
                        aria-pressed={selected}
                      >
                        <span style={{ display: 'block', position: 'relative' }}>
                          <img
                            src={option.preview_url}
                            alt=""
                            className="orientation-preview-img"
                            style={{ width, height }}
                          />
                          {selected && splitSelected && option.orientation === 'landscape' && (
                            <>
                              <span
                                aria-hidden="true"
                                style={{
                                  position: 'absolute',
                                  top: 0,
                                  bottom: 0,
                                  left: '50%',
                                  borderLeft: '2px dashed rgba(70, 54, 34, 0.9)',
                                }}
                              />
                              <span style={{ position: 'absolute', left: '25%', top: 6, transform: 'translateX(-50%)' }}>Page 1</span>
                              <span style={{ position: 'absolute', left: '75%', top: 6, transform: 'translateX(-50%)' }}>Page 2</span>
                            </>
                          )}
                        </span>
                      </button>
                      {option.orientation === 'landscape' && (
                        <label
                          style={{
                            display: 'block',
                            marginTop: 7,
                            textAlign: 'center',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={selected && splitSelected}
                            disabled={!selected}
                            onChange={(event) =>
                              setSplitTwoUpDegrees(event.target.checked ? option.degrees : null)
                            }
                          />{' '}
                          Two columns
                        </label>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
            <div className="orientation-actions">
              <Link
                className="banner-button-rev orientation-cancel-btn"
                to={`/${privateId}/segment`}
              >
                &laquo; Cancel
              </Link>
              <div
                className="banner-button orientation-submit-btn"
                role="button"
                tabIndex={submitting ? -1 : 0}
                aria-disabled={submitting}
                style={submitting ? { opacity: 0.6, cursor: 'default' } : undefined}
                onClick={() => {
                  if (!submitting) void handleReimport()
                }}
                onKeyDown={(e) => {
                  if (submitting) return
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    void handleReimport()
                  }
                }}
              >
                Reorient &raquo;
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </Layout>
  )
}
