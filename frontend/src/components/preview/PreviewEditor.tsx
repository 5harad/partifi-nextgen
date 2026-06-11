import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  combineParts,
  getCsrfToken,
  getPreviewData,
  saveLayout,
  startPartGeneration,
} from '../../lib/api'
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
import type { PreviewDataResponse } from '../../types/preview'

const SLIDER_RANGE = 46

type Mode = 'spacing' | 'combine'

type Props = {
  privateId: string
}

export function PreviewEditor({ privateId }: Props) {
  const navigate = useNavigate()
  const [data, setData] = useState<PreviewDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
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

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const preview = await getPreviewData(privateId)
        if (cancelled) return
        setData(preview)
        setBreaks(preview.breaks)
        setSpacings(preview.spacings)
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
    })()
    return () => {
      cancelled = true
    }
  }, [privateId, navigate])

  const allPartNames = useMemo(
    () => (data ? [...data.part_names, ...combinedPartNames] : []),
    [data, combinedPartNames],
  )

  const cues = useMemo(
    () => (part ? computeCues(part, partSegments) : new Set<number>()),
    [part, partSegments],
  )

  const layout = useMemo(() => {
    if (!data || !part || !partSegments[part]) return { chunks: [] as number[][], numPages: 1 }
    const segList = partSegments[part]
    const spacingPx = spacingHighres(spacings[part] ?? 0.1)
    const partBreaks = breaks[part] ?? []
    const chunks = pageChunks(segList, data.segment_heights, spacingPx, partBreaks)
    return { chunks, numPages: chunks.length }
  }, [data, part, partSegments, spacings, breaks])

  useEffect(() => {
    setPageNum((p) => Math.min(p, layout.numPages))
  }, [layout.numPages])

  useEffect(() => {
    const spacing = spacings[part] ?? 0.1
    setSliderUpTop(spacingToSliderUpTop(spacing))
  }, [part, spacings])

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
    draggingSlider.current = which
  }

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingSlider.current) return
      const barId =
        draggingSlider.current === 'down'
          ? 'spacing-scroll-bar-bottom'
          : 'spacing-scroll-bar-top'
      const bar = document.getElementById(barId)
      if (!bar) return
      const rect = bar.getBoundingClientRect()
      const handleTop = Math.max(0, Math.min(SLIDER_RANGE, e.clientY - rect.top))
      const upTop =
        draggingSlider.current === 'down'
          ? SLIDER_RANGE - handleTop
          : handleTop
      const snapped = applySliderSnap(Math.round(upTop))
      setSliderUpTop(snapped)
      setSpacings((prev) => ({ ...prev, [part]: sliderUpTopToSpacing(snapped) }))
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
  }, [part])

  const handlePartifi = async () => {
    try {
      const csrf = await getCsrfToken()
      await saveLayout(privateId, { breaks, spacings }, csrf)
      await startPartGeneration(privateId, csrf)
      navigate(`/${privateId}/partgen`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start part generation')
    }
  }

  const handleEditSegments = async () => {
    const csrf = await getCsrfToken()
    await saveLayout(privateId, { breaks, spacings }, csrf)
    navigate(`/${privateId}/segment`)
  }

  const handleCombine = async () => {
    const partsToCombine = [...selectedParts]
    if (partsToCombine.length < 2) {
      window.alert('Please select at least two parts to combine.')
      return
    }
    const combinedName = partsToCombine.join(' + ')
    if (combinedPartNames.includes(combinedName)) return

    let merged: number[] = []
    for (const p of partsToCombine) {
      merged = merged.concat(partSegments[p] ?? [])
    }
    merged = uniqueSorted(merged)

    setCombinedPartNames((prev) => [...prev, combinedName])
    setPartSegments((prev) => ({ ...prev, [combinedName]: merged }))
    setBreaks((prev) => ({ ...prev, [combinedName]: [] }))
    setSpacings((prev) => ({ ...prev, [combinedName]: 0.1 }))
    setSelectedParts(new Set())

    const csrf = await getCsrfToken()
    await combineParts(privateId, 'add', combinedName, csrf)
  }

  const handleRemoveCombined = async (partName: string) => {
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
    if (part === partName) setPart(allPartNames[0] ?? '')

    const csrf = await getCsrfToken()
    await combineParts(privateId, 'remove', partName, csrf)
  }

  if (error) {
    return (
      <div id="main" style={{ height: '750px', padding: '40px' }}>
        <p className="red">{error}</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div id="main" style={{ height: '750px' }}>
        <div id="transition">
          <div id="transition-text">Preparing preview…</div>
        </div>
      </div>
    )
  }

  const spacingPx = spacingLowres(spacings[part] ?? 0.1)
  const partBreaks = breaks[part] ?? []
  const canGoPrev = pageNum > 1
  const canGoNext = pageNum < layout.numPages
  const navDisabledStyle = { color: 'gray', cursor: 'default' as const }

  return (
    <div id="main">
      <img
        src="/images/notes_bg.jpg"
        width={1190}
        height={252}
        style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
        alt=""
      />
      <div id="preview-pane">
        <img src="/images/music-stand-header_bg.gif" alt="" />
        <div id="preview-header">STEP 3. &nbsp; Preview the parts</div>
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
              <div id="part-pages" style={{ left: `${-380 * (pageNum - 1)}px` }}>
                {layout.chunks.map((chunk, chunkIdx) => (
                  <div
                    key={chunkIdx}
                    className="part-page"
                    style={chunkIdx > 0 ? { left: `${chunkIdx * 380}px` } : undefined}
                  >
                    {chunk.map((segId, segIndexInPart) => {
                      const globalIndex = partSegments[part]?.indexOf(segId) ?? segIndexInPart
                      const lrH = lowresHeight(data.segment_heights[segId])
                      const lrW = lowresWidth(data.segment_widths[segId])
                      const isCue = cues.has(segId)
                      const hasBreakAfter = partBreaks.includes(globalIndex)
                      return (
                        <div key={segId}>
                          <div
                            className={`partseg${isCue ? ' cue' : ''}`}
                            style={{
                              height: lrH,
                              marginBottom: hasBreakAfter ? 5 : spacingPx,
                            }}
                            onClick={() => toggleBreak(globalIndex)}
                            onMouseEnter={() => setHoverSeg(globalIndex)}
                            onMouseLeave={() => setHoverSeg(null)}
                            role="presentation"
                          >
                            {data.segment_labels[segId] && (
                              <div
                                className="rotate"
                                style={{ width: lrH - 2, top: lrH }}
                              >
                                {data.segment_labels[segId]}
                              </div>
                            )}
                            <img
                              src={data.segment_urls[String(segId)]}
                              width={lrW}
                              height={lrH}
                              style={{ left: data.left_margin }}
                              alt=""
                            />
                            {hoverSeg === globalIndex &&
                              !partBreaks.includes(globalIndex) && (
                                <div
                                  className="proposed-break"
                                  style={{
                                    top:
                                      lrH +
                                      Math.min(10, Math.round(spacingPx / 2)),
                                  }}
                                />
                              )}
                          </div>
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
              Select two or more parts to create a new, combined part.
            </div>
            <div id="part-combine-selector-pane">
              <div
                id="combine-now-button"
                onClick={handleCombine}
                role="button"
                tabIndex={0}
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
          tabIndex={0}
        >
          Partifi it &raquo;
        </div>
        <div
          id="edit-segs-button"
          className="banner-button-rev"
          onClick={handleEditSegments}
          role="button"
          tabIndex={0}
        >
          &laquo; Edit segments
        </div>
      </div>
    </div>
  )
}
