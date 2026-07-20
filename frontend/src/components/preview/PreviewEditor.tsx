import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  combineParts,
  getCsrfToken,
  getPreviewData,
  retryPartsetPageCache,
  saveLayout,
  startPartGeneration,
} from '../../lib/api'
import { displayPartName } from '../../lib/partNames'
import {
  abbreviate,
  applySliderSnap,
  computeCues,
  lowresHeight,
  lowresWidth,
  pageChunks,
  spacingHighres,
  spacingLowres,
  sliderUpTopToSpacing,
  spacingToSliderUpTop,
  uniqueSorted,
} from '../../lib/previewUtils'
import { getPreviewPageStride, getPageBreakMarkerWidth } from '../../lib/pageDimensions'
import {
  getPreviewPageLayout,
  pasteLeftMarginPx,
  previewPageCssVars,
  segmentLabelLayout,
} from '../../lib/previewPageLayout'
import { useSessionImageCache, type SessionImageRequest } from '../../lib/useSessionImageCache'
import { previewHeaderFontFamily } from '../../lib/previewHeaderFont'
import { TransitionError, TransitionErrorButton } from '../TransitionError'
import { TransitionWait } from '../TransitionWait'
import type { PreviewDataResponse } from '../../types/preview'

const SLIDER_RANGE = 46
const MAX_COMBINE_PARTS = 10
const PREPARING_INDICATOR_DELAY_MS = 200

type Mode = 'spacing' | 'combine'

type Props = {
  privateId: string
  onPreparingChange?: (preparing: boolean) => void
}

type LayoutSnapshot = {
  breaks: Record<string, number[]>
  spacings: Record<string, number>
}

function cloneLayoutSnapshot(breaks: Record<string, number[]>, spacings: Record<string, number>): LayoutSnapshot {
  return {
    breaks: Object.fromEntries(Object.entries(breaks).map(([part, values]) => [part, [...values]])),
    spacings: { ...spacings },
  }
}

function layoutsAreEqual(
  breaks: Record<string, number[]>,
  spacings: Record<string, number>,
  baseline: LayoutSnapshot,
): boolean {
  const breakParts = new Set([...Object.keys(breaks), ...Object.keys(baseline.breaks)])
  for (const part of breakParts) {
    const current = [...(breaks[part] ?? [])].sort((a, b) => a - b)
    const saved = [...(baseline.breaks[part] ?? [])].sort((a, b) => a - b)
    if (current.length !== saved.length || current.some((value, index) => value !== saved[index])) {
      return false
    }
  }

  const spacingParts = new Set([...Object.keys(spacings), ...Object.keys(baseline.spacings)])
  for (const part of spacingParts) {
    if ((spacings[part] ?? 0.1) !== (baseline.spacings[part] ?? 0.1)) return false
  }
  return true
}

export function PreviewEditor({ privateId, onPreparingChange }: Props) {
  const navigate = useNavigate()
  const [data, setData] = useState<PreviewDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showPreparingIndicator, setShowPreparingIndicator] = useState(false)
  const [cacheError, setCacheError] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [saving, setSaving] = useState(false)
  const [mode, setMode] = useState<Mode>('spacing')
  const [part, setPart] = useState<string>('')
  const [pageNum, setPageNum] = useState(1)
  const [breaks, setBreaks] = useState<Record<string, number[]>>({})
  const [spacings, setSpacings] = useState<Record<string, number>>({})
  const [partSegments, setPartSegments] = useState<Record<string, number[]>>({})
  const [combinedPartNames, setCombinedPartNames] = useState<string[]>([])
  const [selectedParts, setSelectedParts] = useState<Set<string>>(new Set())
  const [hoverSeg, setHoverSeg] = useState<number | null>(null)
  const [sliderUpTop, setSliderUpTop] = useState(42)
  const draggingSlider = useRef<'up' | 'down' | null>(null)
  const sliderGrabOffsetY = useRef(0)
  const sliderUpTopRef = useRef(sliderUpTop)
  const partRef = useRef(part)
  const [reloadToken, setReloadToken] = useState(0)
  const [pageTransition, setPageTransition] = useState(false)
  const saveInFlightRef = useRef(false)
  const layoutBaselineRef = useRef<LayoutSnapshot>({ breaks: {}, spacings: {} })

  useEffect(() => {
    const onPageShow = (event: PageTransitionEvent) => {
      if (!event.persisted) return
      setData(null)
      setError(null)
      setShowPreparingIndicator(false)
      setCacheError(false)
      setReloadToken((token) => token + 1)
    }
    window.addEventListener('pageshow', onPageShow)
    return () => window.removeEventListener('pageshow', onPageShow)
  }, [])

  useEffect(() => {
    let cancelled = false
    let timeoutId: number
    let pollCount = 0

    const load = async () => {
      try {
        const preview = await getPreviewData(privateId)
        if (cancelled) return

        if (!preview.images_ready) {
          if (preview.image_cache_error_message) {
            setCacheError(true)
            setError(preview.image_cache_error_message)
            return
          }
          setCacheError(false)
          setError(null)
          pollCount += 1
          if (pollCount >= 300) {
            setError(
              'Score images are taking longer than expected. Please refresh the page in a few minutes.',
            )
            return
          }
          timeoutId = window.setTimeout(load, 2000)
          return
        }

        setData(preview)
        setShowPreparingIndicator(false)
        setBreaks(preview.breaks)
        setSpacings(preview.spacings)
        layoutBaselineRef.current = cloneLayoutSnapshot(preview.breaks, preview.spacings)
        setPartSegments(preview.part_segments)
        setCombinedPartNames(preview.combined_part_names)
        const all = [...preview.part_names, ...preview.combined_part_names]
        setPart(all[0] ?? '')
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to load preview'
          if (msg.includes('No parts')) {
            navigate(`/${privateId}/segment`)
          } else {
            setError(msg)
          }
        }
      }
    }

    load()
    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [privateId, navigate, reloadToken])

  useEffect(() => {
    if (data || error) return
    const timeoutId = window.setTimeout(
      () => setShowPreparingIndicator(true),
      PREPARING_INDICATOR_DELAY_MS,
    )
    return () => window.clearTimeout(timeoutId)
  }, [data, error])

  useEffect(() => {
    onPreparingChange?.(!data && !error)
  }, [data, error, onPreparingChange])

  const allPartNames = useMemo(
    () => (data ? [...data.part_names, ...combinedPartNames] : []),
    [data, combinedPartNames],
  )

  const cues = useMemo(
    () => (part ? computeCues(part, partSegments) : new Set<number>()),
    [part, partSegments],
  )

  const partLeftMargin = useMemo(() => {
    if (!data || !part) return 0
    const segList = partSegments[part]
    if (!segList?.length) return 0
    const orientation = data.orientation ?? 'portrait'
    let maxWidth = 0
    for (const segId of segList) {
      maxWidth = Math.max(maxWidth, data.segment_widths[segId] ?? 0)
    }
    return pasteLeftMarginPx(maxWidth, orientation)
  }, [data, part, partSegments])

  const layout = useMemo(() => {
    if (!data || !part || !partSegments[part]) return { chunks: [] as number[][], numPages: 1 }
    const orientation = data.orientation ?? 'portrait'
    const segList = partSegments[part]
    const spacingPx = spacingHighres(spacings[part] ?? 0.1)
    const partBreaks = breaks[part] ?? []
    const chunks = pageChunks(segList, data.segment_heights, spacingPx, partBreaks, orientation)
    return { chunks, numPages: chunks.length }
  }, [data, part, partSegments, spacings, breaks])

  useEffect(() => {
    setPageTransition(false)
    const frame = requestAnimationFrame(() => {
      requestAnimationFrame(() => setPageTransition(true))
    })
    return () => cancelAnimationFrame(frame)
  }, [data?.orientation, part, layout.numPages])

  useEffect(() => {
    setPageNum((p) => Math.min(p, layout.numPages))
  }, [layout.numPages])

  const sessionImageRequests = useMemo<SessionImageRequest[]>(() => {
    if (!data) return []

    const highPrioritySegmentIds: number[] = []
    const highPrioritySegments = new Set<number>()
    for (const name of [...data.part_names, ...data.combined_part_names]) {
      const chunks = pageChunks(
        data.part_segments[name] ?? [],
        data.segment_heights,
        spacingHighres(data.spacings[name] ?? 0.1),
        data.breaks[name] ?? [],
        data.orientation ?? 'portrait',
      )
      for (const segmentId of chunks.slice(0, 2).flat()) {
        if (!highPrioritySegments.has(segmentId)) {
          highPrioritySegments.add(segmentId)
          highPrioritySegmentIds.push(segmentId)
        }
      }
    }

    const high = highPrioritySegmentIds.flatMap((segmentId) => {
      const url = data.segment_urls[String(segmentId)]
      return url ? [{ key: url, url, priority: 'high' as const }] : []
    })
    const low = Object.entries(data.segment_urls).flatMap(([segmentId, url]) =>
      highPrioritySegments.has(Number(segmentId))
        ? []
        : [{ key: url, url, priority: 'low' as const }],
    )
    return [...high, ...low]
  }, [data])
  const sessionImageUrls = useSessionImageCache(sessionImageRequests, data)

  useEffect(() => {
    const spacing = spacings[part] ?? 0.1
    setSliderUpTop(spacingToSliderUpTop(spacing))
  }, [part, spacings])

  useEffect(() => {
    sliderUpTopRef.current = sliderUpTop
  }, [sliderUpTop])

  useEffect(() => {
    partRef.current = part
  }, [part])

  const applySliderFromClientY = useCallback((clientY: number, which: 'up' | 'down') => {
    const barId =
      which === 'down' ? 'spacing-scroll-bar-bottom' : 'spacing-scroll-bar-top'
    const bar = document.getElementById(barId)
    if (!bar) return
    const rect = bar.getBoundingClientRect()
    const handleTop = Math.max(
      0,
      Math.min(SLIDER_RANGE, clientY - rect.top - sliderGrabOffsetY.current),
    )
    const upTop = which === 'down' ? SLIDER_RANGE - handleTop : handleTop
    const snapped = applySliderSnap(Math.round(upTop))
    setSliderUpTop(snapped)
    setSpacings((prev) => ({ ...prev, [partRef.current]: sliderUpTopToSpacing(snapped) }))
  }, [])

  const toggleBreak = useCallback(
    (segIndex: number) => {
      if (!part) return
      setBreaks((prev) => {
        const current = [...(prev[part] ?? [])]
        const ndx = current.indexOf(segIndex)
        if (ndx === -1) current.push(segIndex)
        else current.splice(ndx, 1)
        return { ...prev, [part]: current }
      })
    },
    [part],
  )

  const handleSliderMouseDown = (which: 'up' | 'down') => (e: React.MouseEvent) => {
    e.preventDefault()
    const barId =
      which === 'down' ? 'spacing-scroll-bar-bottom' : 'spacing-scroll-bar-top'
    const bar = document.getElementById(barId)
    if (!bar) return
    const rect = bar.getBoundingClientRect()
    const currentHandleTop =
      which === 'down' ? SLIDER_RANGE - sliderUpTopRef.current : sliderUpTopRef.current
    sliderGrabOffsetY.current = e.clientY - rect.top - currentHandleTop
    draggingSlider.current = which
    applySliderFromClientY(e.clientY, which)
  }

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingSlider.current) return
      applySliderFromClientY(e.clientY, draggingSlider.current)
    }
    const onUp = () => {
      draggingSlider.current = null
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [applySliderFromClientY])

  const handlePartifi = async () => {
    if (saveInFlightRef.current) return
    saveInFlightRef.current = true
    try {
      setSaving(true)
      const csrf = await getCsrfToken()
      if (!layoutsAreEqual(breaks, spacings, layoutBaselineRef.current)) {
        await saveLayout(privateId, { breaks, spacings }, csrf)
        layoutBaselineRef.current = cloneLayoutSnapshot(breaks, spacings)
      }
      const generation = await startPartGeneration(privateId, csrf)
      navigate(generation.parts_ready ? `/${privateId}` : `/${privateId}/partgen`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start part generation')
    } finally {
      saveInFlightRef.current = false
      setSaving(false)
    }
  }

  const handleEditSegments = async () => {
    if (saveInFlightRef.current) return
    saveInFlightRef.current = true
    try {
      setSaving(true)
      if (!layoutsAreEqual(breaks, spacings, layoutBaselineRef.current)) {
        const csrf = await getCsrfToken()
        await saveLayout(privateId, { breaks, spacings }, csrf)
        layoutBaselineRef.current = cloneLayoutSnapshot(breaks, spacings)
      }
      navigate(`/${privateId}/segment`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save preview layout')
    } finally {
      saveInFlightRef.current = false
      setSaving(false)
    }
  }

  const handleCombine = async () => {
    if (saveInFlightRef.current) return
    const partsToCombine = [...selectedParts]
    if (partsToCombine.length < 2) {
      window.alert('Please select at least two parts to combine.')
      return
    }
    if (partsToCombine.length > MAX_COMBINE_PARTS) {
      window.alert(`Please select at most ${MAX_COMBINE_PARTS} parts to combine.`)
      return
    }
    const combinedName = partsToCombine.join(' + ')
    if (combinedPartNames.includes(combinedName)) return

    saveInFlightRef.current = true
    let merged: number[] = []
    for (const p of partsToCombine) {
      merged = merged.concat(partSegments[p] ?? [])
    }
    merged = uniqueSorted(merged)

    try {
      setSaving(true)
      const csrf = await getCsrfToken()
      await combineParts(privateId, 'add', combinedName, csrf)
      setCombinedPartNames((prev) => [...prev, combinedName])
      setPartSegments((prev) => ({ ...prev, [combinedName]: merged }))
      setBreaks((prev) => ({ ...prev, [combinedName]: [] }))
      setSpacings((prev) => ({ ...prev, [combinedName]: 0.1 }))
      layoutBaselineRef.current = {
        breaks: { ...layoutBaselineRef.current.breaks, [combinedName]: [] },
        spacings: { ...layoutBaselineRef.current.spacings, [combinedName]: 0.1 },
      }
      setSelectedParts(new Set())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to combine parts')
    } finally {
      saveInFlightRef.current = false
      setSaving(false)
    }
  }

  const handleRemoveCombined = async (partName: string) => {
    if (saveInFlightRef.current) return
    saveInFlightRef.current = true

    try {
      setSaving(true)
      const csrf = await getCsrfToken()
      await combineParts(privateId, 'remove', partName, csrf)
      setCombinedPartNames((prev) => prev.filter((p) => p !== partName))
      setPartSegments((prev) => {
        const next = { ...prev }
        delete next[partName]
        return next
      })
      setBreaks((prev) => {
        const next = { ...prev }
        delete next[partName]
        return next
      })
      setSpacings((prev) => {
        const next = { ...prev }
        delete next[partName]
        return next
      })
      const nextBreaks = { ...layoutBaselineRef.current.breaks }
      const nextSpacings = { ...layoutBaselineRef.current.spacings }
      delete nextBreaks[partName]
      delete nextSpacings[partName]
      layoutBaselineRef.current = { breaks: nextBreaks, spacings: nextSpacings }
      if (part === partName) {
        setPart(
          [...(data?.part_names ?? []), ...combinedPartNames.filter((name) => name !== partName)][0] ??
            '',
        )
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove combined part')
    } finally {
      saveInFlightRef.current = false
      setSaving(false)
    }
  }

  const handleRetryPageCache = async () => {
    if (retrying) return
    setRetrying(true)
    try {
      const token = await getCsrfToken()
      await retryPartsetPageCache(privateId, token)
      setError(null)
      setCacheError(false)
      setReloadToken((token) => token + 1)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to retry page images'
      setError(message)
      setCacheError(true)
    } finally {
      setRetrying(false)
    }
  }

  if (error) {
    return (
      <TransitionError message={error}>
        {cacheError ? (
          <TransitionErrorButton
            label={retrying ? 'Retrying…' : 'Try again'}
            onClick={handleRetryPageCache}
            disabled={retrying}
          />
        ) : null}
      </TransitionError>
    )
  }

  if (!data) {
    if (!showPreparingIndicator) return null
    return (
      <TransitionWait
        message="Please wait while we prepare the score"
        indeterminate
      />
    )
  }

  const orientation = data.orientation ?? 'portrait'
  const isLandscape = orientation === 'landscape'
  const pageLayout = getPreviewPageLayout(orientation)
  const pageStride = getPreviewPageStride(orientation)
  const pageBreakWidth = getPageBreakMarkerWidth(orientation)
  const headerFontFamily = previewHeaderFontFamily(
    data.title ?? '',
    data.composer ?? '',
    part,
    data.partset_id,
  )
  const previewPaneStyle = {
    ...previewPageCssVars(pageLayout),
    '--page-break-width': `${pageBreakWidth}px`,
    '--page-break-delete-left': `${pageBreakWidth - 15}px`,
    '--part-page-font-family': headerFontFamily,
  } as React.CSSProperties
  const spacingPx = spacingLowres(spacings[part] ?? 0.1, orientation)
  const partBreaks = breaks[part] ?? []
  const canGoPrev = pageNum > 1
  const canGoNext = pageNum < layout.numPages
  const visibleChunks = layout.chunks
    .map((chunk, chunkIdx) => ({ chunk, chunkIdx }))
    .filter(({ chunkIdx }) => chunkIdx >= pageNum - 1 && chunkIdx <= pageNum)
  const navDisabledStyle = { color: 'gray', cursor: 'default' as const }
  const saveDisabledStyle = saving ? { opacity: 0.6, cursor: 'default' as const } : undefined

  return (
    <div id="main" className="canvas-page">
      <img
        src="/images/notes_bg.jpg"
        width={1190}
        height={252}
        style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
        alt=""
      />
      <img
        className="stand-figure-img"
        src="/images/music-stand-header-long.gif"
        width={949}
        alt=""
      />
      <div
        id="preview-pane"
        className={isLandscape ? 'orientation-landscape' : undefined}
        style={{ ...previewPaneStyle, pointerEvents: saving ? 'none' : undefined }}
        inert={saving}
      >
        <div id="preview-header">
          STEP 3. &nbsp; Preview the parts{saving ? ' (saving…)' : ''}
        </div>
        <div
          id="adjust-spacing"
          className={`import-button${mode === 'spacing' ? ' import-button-down' : ''}`}
          onClick={() => setMode('spacing')}
          role="button"
          tabIndex={0}
        >
          adjust spacing
        </div>
        <div
          id="combine-parts"
          className={`import-button${mode === 'combine' ? ' import-button-down' : ''}`}
          onClick={() => setMode('combine')}
          role="button"
          tabIndex={0}
        >
          combine parts
        </div>

        {mode === 'spacing' && (
          <>
            <div id="part-pages-viewer">
              <div
                id="part-pages"
                className={pageTransition ? 'part-pages-animated' : undefined}
                style={{ left: `${-pageStride * (pageNum - 1)}px` }}
              >
                {visibleChunks.map(({ chunk, chunkIdx }) => (
                    <div
                      key={chunkIdx}
                      className="part-page"
                      style={chunkIdx > 0 ? { left: `${chunkIdx * pageStride}px` } : undefined}
                    >
                      <img
                        className="part-page-logo"
                        src="/images/scroll.png"
                        width={pageLayout.logoSize}
                        height={pageLayout.logoSize}
                        alt=""
                      />
                      {data.title ? (
                        <div className="part-page-title">{data.title}</div>
                      ) : null}
                      {data.composer ? (
                        <div className="part-page-composer">{data.composer}</div>
                      ) : null}
                      <div className="part-page-part-name">{displayPartName(part)}</div>
                      <span className="part-page-partifi-id">
                        partifi.org/{data.partset_id}
                      </span>
                      <div className="part-page-rule" />
                      <div className="part-page-content">
                    {chunk.map((segId, segIndexInPart) => {
                      const globalIndex = partSegments[part]?.indexOf(segId) ?? segIndexInPart
                      const lrH = lowresHeight(data.segment_heights[segId], orientation)
                      const lrW = lowresWidth(data.segment_widths[segId], orientation)
                      const isCue = cues.has(segId)
                      const hasBreakAfter = partBreaks.includes(globalIndex)
                      const isLastOnPage = segIndexInPart === chunk.length - 1
                      const marginBottom = hasBreakAfter
                        ? isLastOnPage
                          ? 0
                          : 5
                        : isLastOnPage
                          ? 0
                          : spacingPx
                      return (
                        <div key={segId} className="part-segment-slot">
                          <div
                            className={`partseg${isCue ? ' cue' : ''}`}
                            style={{
                              height: lrH,
                              marginBottom,
                            }}
                            onClick={() => toggleBreak(globalIndex)}
                            onMouseEnter={() => setHoverSeg(globalIndex)}
                            onMouseLeave={() => setHoverSeg(null)}
                            role="presentation"
                          >
                            {data.segment_labels[segId] && (() => {
                              const labelBox = segmentLabelLayout(
                                lrH,
                                partLeftMargin,
                                orientation,
                              )
                              return (
                                <div
                                  className="segment-label-box"
                                  style={{
                                    left: labelBox.left,
                                    top: labelBox.top,
                                    width: labelBox.width,
                                    height: labelBox.height,
                                    fontSize: labelBox.fontSize,
                                  }}
                                >
                                  <span className="segment-label-text">
                                    {data.segment_labels[segId]}
                                  </span>
                                </div>
                              )
                            })()}
                            {sessionImageUrls[data.segment_urls[String(segId)]] ? (
                              <img
                                src={sessionImageUrls[data.segment_urls[String(segId)]]}
                                width={lrW}
                                height={lrH}
                                style={{ left: partLeftMargin }}
                                alt=""
                              />
                            ) : null}
                          </div>
                          {hoverSeg === globalIndex &&
                            !partBreaks.includes(globalIndex) && (
                              <div
                                className="proposed-break"
                                style={{
                                  top: lrH + marginBottom / 2,
                                }}
                              />
                            )}
                          {hasBreakAfter && (
                            <div className="page-break">
                              page break
                              <div
                                className="page-break-delete"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  toggleBreak(globalIndex)
                                }}
                                role="presentation"
                              />
                            </div>
                          )}
                        </div>
                      )
                    })}
                    </div>
                    <div className="part-page-footer">Page {chunkIdx + 1}</div>
                  </div>
                ))}
              </div>
            </div>

            <div id="scrollbar1">
              <div className="viewport">
                <div id="part-menu" className="overview">
                  {allPartNames.map((partName) => (
                    <div
                      key={partName}
                      className="part-menu-item"
                      style={
                        part === partName
                          ? { backgroundImage: "url('/images/arrow_bg.gif')" }
                          : undefined
                      }
                      onClick={() => {
                        setPart(partName)
                        setPageNum(1)
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="part-menu-item-txt">
                        <span title={partName}>
                          {partName.length > 20 ? abbreviate(partName) : partName}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div id="part-nav-bar">
              <div id="part-page-num">
                page {pageNum} of {layout.numPages}
              </div>
              <div id="part-prev-page">
                {canGoPrev ? (
                  <a
                    href="#"
                    className="red"
                    onClick={(e) => {
                      e.preventDefault()
                      setPageNum(pageNum - 1)
                    }}
                  >
                    &laquo; previous
                  </a>
                ) : (
                  <span style={navDisabledStyle}>&laquo; previous</span>
                )}
              </div>
              <div id="part-next-page">
                {canGoNext ? (
                  <a
                    href="#"
                    className="red"
                    onClick={(e) => {
                      e.preventDefault()
                      setPageNum(pageNum + 1)
                    }}
                  >
                    next &raquo;
                  </a>
                ) : (
                  <span style={navDisabledStyle}>next &raquo;</span>
                )}
              </div>
            </div>

            <div id="spacing-widget">
              line spacing
              <div id="spacing-scroll-bar">
                <div id="spacing-scroll-bar-top">
                  <div id="slider-up-snap" />
                  <div
                    id="slider-up"
                    style={{ top: sliderUpTop }}
                    onMouseDown={handleSliderMouseDown('up')}
                    role="presentation"
                  />
                </div>
                <div id="spacing-scroll-bar-bottom">
                  <div id="slider-down-snap" />
                  <div
                    id="slider-down"
                    style={{ top: SLIDER_RANGE - sliderUpTop }}
                    onMouseDown={handleSliderMouseDown('down')}
                    role="presentation"
                  />
                </div>
              </div>
            </div>
          </>
        )}

        {mode === 'combine' && (
          <>
            <div id="combine-instructions">
              Select two or more parts (up to {MAX_COMBINE_PARTS}) to create a new, combined part.
            </div>
            <div id="part-combine-selector-pane">
              <div
                id="combine-now-button"
                onClick={handleCombine}
                role="button"
                tabIndex={saving ? -1 : 0}
                aria-disabled={saving}
                style={saveDisabledStyle}
              >
                Combine
              </div>
            </div>
            <div id="scrollbar2" style={{ display: 'block' }}>
              <div className="viewport">
                <div id="part-selector" className="overview">
                  {data.part_names.map((partName) => (
                    <div key={partName} className="part-selector-item">
                      <div className="part-selector-item-txt">
                        <div
                          className="checkbox"
                          onClick={() => {
                            setSelectedParts((prev) => {
                              const next = new Set(prev)
                              if (next.has(partName)) next.delete(partName)
                              else next.add(partName)
                              return next
                            })
                          }}
                          role="presentation"
                        >
                          <div
                            className="check"
                            style={
                              selectedParts.has(partName)
                                ? { display: 'block' }
                                : undefined
                            }
                          />
                        </div>
                        <span title={partName}>
                          {partName.length > 25 ? abbreviate(partName) : partName}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div id="scrollbar3" style={{ display: 'block' }}>
              <div className="viewport">
                <div id="combined-parts" className="overview">
                  {combinedPartNames.map((partName) => (
                    <div key={partName} className="combined-part-selector-item">
                      <div className="combined-part-selector-item-txt">
                        <div
                          className="combined-part-delete"
                          data-partname={partName}
                          onClick={() => handleRemoveCombined(partName)}
                          role="presentation"
                          aria-disabled={saving}
                          style={saveDisabledStyle}
                        />
                        <span title={partName}>
                          {partName.length > 28 ? abbreviate(partName) : partName}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        <div
          id="partifi-button"
          className="banner-button"
          onClick={handlePartifi}
          role="button"
          tabIndex={saving ? -1 : 0}
          aria-disabled={saving}
          style={saveDisabledStyle}
        >
          Partifi it &raquo;
        </div>
        <div
          id="edit-segs-button"
          className="banner-button-rev"
          onClick={handleEditSegments}
          role="button"
          tabIndex={saving ? -1 : 0}
          aria-disabled={saving}
          style={saveDisabledStyle}
        >
          &laquo; Edit segments
        </div>
      </div>
    </div>
  )
}
