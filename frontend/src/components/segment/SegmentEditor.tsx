import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCsrfToken, savePageSegments } from '../../lib/api'
import {
  applySuggestionsToRegions,
  buildTagList,
  nextTagsRegionId,
} from '../../lib/segmentTagSuggestions'
import { TagsInput } from './TagsInput'
import {
  VIEWER_HEIGHT,
  VIEWER_WIDTH,
  MIN_SEGMENT_GAP,
  buildPageData,
  clampSegmentTopPx,
  computeRegionLayouts,
  marginPctToPx,
  marginPxToPct,
  materializeAllPagesWithSuggestions,
  minDistanceToSegments,
  nextRegionId,
  pageDataAreEqual,
  regionsFromPageData,
} from '../../lib/segmentUtils'
import type { PageSegmentData, RegionState, SegmentDataResponse } from '../../types/segment'

type Props = {
  data: SegmentDataResponse
}

export function SegmentEditor({ data }: Props) {
  const navigate = useNavigate()
  const segmenterRef = useRef<HTMLDivElement>(null)
  const sliderRef = useRef<HTMLDivElement>(null)

  const [pagesData, setPagesData] = useState(() => {
    const pages = { ...data.pages }
    for (let p = 1; p <= data.num_pages; p++) {
      const key = `p${p}`
      if (!pages[key]) {
        pages[key] = { left_margin: 0, right_margin: 100, rotation: 0, segments: [] }
      }
    }
    return pages
  })

  const [pageNum, setPageNum] = useState(1)
  const [previewerStart, setPreviewerStart] = useState(1)
  const [regions, setRegions] = useState<RegionState[]>(() =>
    regionsFromPageData(pagesData.p1 ?? { left_margin: 0, right_margin: 100, rotation: 0, segments: [] }),
  )
  const [leftMarginPx, setLeftMarginPx] = useState(() =>
    marginPctToPx(pagesData.p1?.left_margin ?? 0),
  )
  const [rightMarginPx, setRightMarginPx] = useState(() =>
    marginPctToPx(pagesData.p1?.right_margin ?? 100),
  )
  const [rotation, setRotation] = useState(pagesData.p1?.rotation ?? 0)
  const serverPageDataRef = useRef<PageSegmentData>(
    JSON.parse(JSON.stringify(pagesData.p1 ?? { left_margin: 0, right_margin: 100, rotation: 0, segments: [] })),
  )

  const [tagList, setTagList] = useState<string[]>(() => buildTagList(pagesData, data.num_pages))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const focusedLabelIdRef = useRef<string | null>(null)
  const focusedTagsIdRef = useRef<string | null>(null)
  const tagInputRefs = useRef<Record<string, HTMLInputElement | null>>({})
  const suppressTagBlurRef = useRef(false)
  const suppressSegmenterClickRef = useRef(false)
  const segmentDragStartYRef = useRef(0)

  const stateRef = useRef({
    regions,
    leftMarginPx,
    rightMarginPx,
    rotation,
    pageNum,
    pagesData,
  })
  useEffect(() => {
    stateRef.current = { regions, leftMarginPx, rightMarginPx, rotation, pageNum, pagesData }
  }, [regions, leftMarginPx, rightMarginPx, rotation, pageNum, pagesData])

  const currentPageKey = `p${pageNum}`
  const pageImageUrl = data.image_urls.lowres[String(pageNum)]
  const layouts = useMemo(() => computeRegionLayouts(regions), [regions])

  const leftMargin = Math.min(leftMarginPx, rightMarginPx)
  const rightMargin = Math.max(leftMarginPx, rightMarginPx)
  const leftGrayWidth = Math.min(leftMarginPx, rightMarginPx) + 7
  const rightGrayWidth = 593 - Math.max(leftMarginPx, rightMarginPx)

  const sliderHandleLeft = Math.min(99, Math.round(50 + -rotation * 5))

  const syncWithSuggestions = useCallback(
    (nextRegions: RegionState[], allPages: Record<string, PageSegmentData>) => {
      const suggested = applySuggestionsToRegions(
        nextRegions,
        allPages,
        pageNum,
        data.num_pages,
        focusedLabelIdRef.current,
        focusedTagsIdRef.current,
      )
      setPagesData(allPages)
      setRegions(suggested)
      setTagList(buildTagList(allPages, data.num_pages))
      return suggested
    },
    [pageNum, data.num_pages],
  )

  const commitRegions = useCallback(
    (nextRegions: RegionState[]) => {
      const pageData = buildPageData(
        nextRegions,
        marginPxToPct(leftMargin),
        marginPxToPct(rightMargin),
        rotation,
      )
      const allPages = { ...stateRef.current.pagesData, [currentPageKey]: pageData }
      return syncWithSuggestions(nextRegions, allPages)
    },
    [currentPageKey, leftMargin, rightMargin, rotation, syncWithSuggestions],
  )

  const refreshSuggestions = useCallback(() => {
    commitRegions(stateRef.current.regions)
  }, [commitRegions])

  const replaceRegions = useCallback(
    (nextRegions: RegionState[]) => {
      const pageData = buildPageData(
        nextRegions,
        marginPxToPct(leftMargin),
        marginPxToPct(rightMargin),
        rotation,
      )
      const allPages = { ...stateRef.current.pagesData, [currentPageKey]: pageData }
      const suggested = applySuggestionsToRegions(
        nextRegions,
        allPages,
        pageNum,
        data.num_pages,
        focusedLabelIdRef.current,
        focusedTagsIdRef.current,
      )
      stateRef.current.regions = suggested
      setPagesData(allPages)
      setRegions(suggested)
      setTagList(buildTagList(allPages, data.num_pages))
      return suggested
    },
    [currentPageKey, leftMargin, rightMargin, rotation, pageNum, data.num_pages],
  )

  useEffect(() => {
    refreshSuggestions()
    // Initial grey suggestions on mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const patchRegion = useCallback(
    (id: string, patch: Partial<RegionState>) => {
      const updated = stateRef.current.regions.map((r) =>
        r.id === id ? { ...r, ...patch } : r,
      )
      replaceRegions(updated)
    },
    [replaceRegions],
  )

  const handleTagDelete = (regionId: string) => {
    focusedTagsIdRef.current = regionId
    const updated = stateRef.current.regions.map((r) =>
      r.id === regionId ? { ...r, tags: '(none)', tagIsSuggestion: false } : r,
    )
    replaceRegions(updated)
    const input = tagInputRefs.current[regionId]
    requestAnimationFrame(() => {
      input?.focus()
      input?.select()
    })
  }

  const handleLabelDelete = (regionId: string) => {
    const updated = stateRef.current.regions.map((r) =>
      r.id === regionId ? { ...r, label: '(none)', labelIsSuggestion: false } : r,
    )
    replaceRegions(updated)
  }

  const getCurrentPageData = useCallback(() => {
    return buildPageData(
      regions,
      marginPxToPct(leftMargin),
      marginPxToPct(rightMargin),
      rotation,
    )
  }, [regions, leftMargin, rightMargin, rotation])

  const persistPage = useCallback(
    async (page: number, pageData: PageSegmentData) => {
      const token = await getCsrfToken()
      await savePageSegments(data.private_id, page, pageData, token)
    },
    [data.private_id],
  )

  const applyPageData = (nextPage: number, allPages: Record<string, PageSegmentData>) => {
    const key = `p${nextPage}`
    const pageData = allPages[key] ?? {
      left_margin: 0,
      right_margin: 100,
      rotation: 0,
      segments: [],
    }
    serverPageDataRef.current = JSON.parse(JSON.stringify(pageData))
    const rawRegions = regionsFromPageData(pageData)
    const suggested = applySuggestionsToRegions(
      rawRegions,
      allPages,
      nextPage,
      data.num_pages,
      null,
      null,
    )
    setRegions(suggested)
    setTagList(buildTagList(allPages, data.num_pages))
    setLeftMarginPx(marginPctToPx(pageData.left_margin))
    setRightMarginPx(marginPctToPx(pageData.right_margin))
    setRotation(pageData.rotation)
    setPageNum(nextPage)
  }

  const changePage = useCallback(
    async (nextPage: number) => {
      const {
        pageNum: current,
        regions: currentRegions,
        leftMarginPx: leftPx,
        rightMarginPx: rightPx,
        rotation: rot,
        pagesData: currentPages,
      } = stateRef.current
      if (nextPage === current) return

      const pageData = buildPageData(
        currentRegions,
        marginPxToPct(Math.min(leftPx, rightPx)),
        marginPxToPct(Math.max(leftPx, rightPx)),
        rot,
      )
      const key = `p${current}`
      const updatedPages = { ...currentPages, [key]: pageData }
      setPagesData(updatedPages)
      setTagList(buildTagList(updatedPages, data.num_pages))

      try {
        if (!pageDataAreEqual(serverPageDataRef.current, pageData)) {
          setSaving(true)
          await persistPage(current, pageData)
          serverPageDataRef.current = JSON.parse(JSON.stringify(pageData))
        }
        applyPageData(nextPage, updatedPages)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Save failed')
      } finally {
        setSaving(false)
      }
    },
    [persistPage, data.num_pages],
  )

  const addRegion = (topPx: number) => {
    const next: RegionState = {
      id: nextRegionId(),
      topPx,
      tags: '',
      tagIsSuggestion: false,
      label: '',
      labelIsSuggestion: false,
    }
    commitRegions([...regions, next])
  }

  const handleSegmenterClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (suppressSegmenterClickRef.current) {
      suppressSegmenterClickRef.current = false
      return
    }
    const target = e.target as HTMLElement
    if (
      target.closest(
        '.seg-handle, .seg-delete, .tag-delete, .rehearsal-nos-delete, input, textarea',
      )
    ) {
      return
    }

    const el = segmenterRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    if (y <= 1 || y >= 775 || x <= 0 || x >= 600) return

    if (minDistanceToSegments(y, regions) <= MIN_SEGMENT_GAP) {
      window.alert('Please do not add a new segment so close to an existing one.')
      return
    }
    addRegion(y)
  }

  const removeRegion = (id: string) => {
    replaceRegions(stateRef.current.regions.filter((r) => r.id !== id))
  }


  const startDrag = (
    e: React.PointerEvent,
    kind: 'segment' | 'left-margin' | 'right-margin' | 'rotation',
    regionId?: string,
  ) => {
    e.preventDefault()
    const target = e.currentTarget as HTMLElement
    target.setPointerCapture(e.pointerId)

    if (kind === 'segment' && regionId) {
      segmentDragStartYRef.current = stateRef.current.regions.find((r) => r.id === regionId)?.topPx ?? 0
    }

    const onMove = (ev: PointerEvent) => {
      if (kind === 'segment' && regionId && segmenterRef.current) {
        const rect = segmenterRef.current.getBoundingClientRect()
        const y = Math.max(0, Math.min(VIEWER_HEIGHT, ev.clientY - rect.top))
        if (Math.abs(y - segmentDragStartYRef.current) > 3) {
          suppressSegmenterClickRef.current = true
        }
        setRegions((prev) => {
          const clamped = clampSegmentTopPx(y, regionId, prev)
          const updated = prev.map((r) => (r.id === regionId ? { ...r, topPx: clamped } : r))
          stateRef.current.regions = updated
          return updated
        })
      } else if (kind === 'left-margin' && segmenterRef.current) {
        const rect = segmenterRef.current.getBoundingClientRect()
        const x = Math.max(0, Math.min(VIEWER_WIDTH, ev.clientX - rect.left))
        setLeftMarginPx(x)
        stateRef.current.leftMarginPx = x
      } else if (kind === 'right-margin' && segmenterRef.current) {
        const rect = segmenterRef.current.getBoundingClientRect()
        const x = Math.max(0, Math.min(VIEWER_WIDTH, ev.clientX - rect.left))
        setRightMarginPx(x)
        stateRef.current.rightMarginPx = x
      } else if (kind === 'rotation' && sliderRef.current) {
        const rect = sliderRef.current.getBoundingClientRect()
        const left = Math.max(0, Math.min(99, ev.clientX - rect.left))
        const deg = 10 - left / 5
        setRotation(deg)
        stateRef.current.rotation = deg
      }
    }

    const onUp = () => {
      target.releasePointerCapture(e.pointerId)
      target.removeEventListener('pointermove', onMove)
      target.removeEventListener('pointerup', onUp)
      const {
        regions: latestRegions,
        leftMarginPx: latestLeft,
        rightMarginPx: latestRight,
        rotation: latestRotation,
        pageNum: latestPage,
        pagesData: latestPages,
      } = stateRef.current
      const pageData = buildPageData(
        latestRegions,
        marginPxToPct(Math.min(latestLeft, latestRight)),
        marginPxToPct(Math.max(latestLeft, latestRight)),
        latestRotation,
      )
      const allPages = { ...latestPages, [`p${latestPage}`]: pageData }
      syncWithSuggestions(latestRegions, allPages)
    }

    target.addEventListener('pointermove', onMove)
    target.addEventListener('pointerup', onUp)
  }

  const handleContinue = async () => {
    const currentPages = { ...pagesData, [currentPageKey]: getCurrentPageData() }
    const allPages = materializeAllPagesWithSuggestions(currentPages, data.num_pages)
    const hasTag = Object.values(allPages).some((page) =>
      page.segments.some((s) => s.tags !== '' && s.tags !== '(none)'),
    )
    if (!hasTag) {
      window.alert('Please label the parts before continuing.')
      return
    }
    try {
      setSaving(true)
      for (let p = 1; p <= data.num_pages; p++) {
        await persistPage(p, allPages[`p${p}`]!)
      }
      navigate(`/${data.private_id}/preview`)
    } catch {
      /* error set */
    } finally {
      setSaving(false)
    }
  }

  const thumbsOffset = -(previewerStart - 1) * 120
  const canGoPrev = pageNum > 1
  const canGoNext = pageNum < data.num_pages
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
      <div id="segment-header">STEP 2. &nbsp; Label each part for separation</div>
      <div id="segment-panel">
        <div id="previewer">
          <div id="thumbs" style={{ left: thumbsOffset }}>
            {Array.from({ length: data.num_pages }, (_, i) => {
              const n = i + 1
              const active = n === pageNum
              return (
                <div
                  key={n}
                  className="thumb"
                  id={`preview-${n}`}
                  style={{
                    left: (n - 1) * 120,
                    color: active ? '#E00000' : 'black',
                  }}
                  onClick={() => void changePage(n)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(ev) => {
                    if (ev.key === 'Enter' || ev.key === ' ') void changePage(n)
                  }}
                >
                  page {n}
                  <br />
                  <div className="img-frame" style={{ borderColor: active ? '#E00000' : '#D8D8C2' }}>
                    <img src={data.image_urls.thumbs[String(n)]} alt={`Page ${n}`} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {previewerStart + 6 <= data.num_pages ? (
          <div
            id="previewer-next"
            className="next-button"
            onClick={() => {
              const next = previewerStart + 6
              setPreviewerStart(next)
              void changePage(next)
            }}
            role="button"
            tabIndex={0}
          >
            &raquo;
          </div>
        ) : null}

        {previewerStart - 6 > 0 ? (
          <div
            id="previewer-back"
            className="next-button"
            onClick={() => {
              const next = previewerStart - 6
              setPreviewerStart(next)
              void changePage(next + 5)
            }}
            role="button"
            tabIndex={0}
          >
            &laquo;
          </div>
        ) : null}

        <div id="systems-title">
          system
          <br />
          markers
        </div>
        <div id="systems" />

        <div id="rotator">
          <div id="slider-label">page rotation</div>
          <div id="slider" ref={sliderRef}>
            <div id="slider-center" />
            <div
              id="slider-handle"
              style={{ left: sliderHandleLeft }}
              onPointerDown={(e) => startDrag(e, 'rotation')}
            />
          </div>
        </div>

        <div id="labels-title">part names</div>
        <div id="labels" />

        <div id="viewer">
          <img
            src={pageImageUrl}
            height={VIEWER_HEIGHT}
            alt={`Score page ${pageNum}`}
            style={{ transform: `rotate(${-rotation}deg)` }}
          />
        </div>

        <div id="margins">
          <div
            id="leftrule-wrapper"
            className="margin-wrapper"
            style={{ left: leftMarginPx - 5 }}
          >
            <div className="rule-line" />
            <img
              className="margin-handle"
              src="/images/slider-top.png"
              alt=""
              onPointerDown={(e) => startDrag(e, 'left-margin')}
            />
          </div>
          <div id="left-margin-gray" style={{ width: leftGrayWidth }} />

          <div
            id="rightrule-wrapper"
            className="margin-wrapper"
            style={{ left: rightMarginPx - 5 }}
          >
            <div className="rule-line" />
            <img
              className="margin-handle"
              src="/images/slider-top.png"
              alt=""
              onPointerDown={(e) => startDrag(e, 'right-margin')}
            />
          </div>
          <div id="right-margin-gray" style={{ width: rightGrayWidth }} />
        </div>

        <div id="segmenter" ref={segmenterRef} onClick={handleSegmenterClick}>
          {regions.map((region) => {
            const layout = layouts.get(region.id)
            if (!layout) return null
            const labelClass = region.labelIsSuggestion ? 'rehearsal-nos suggestions' : 'rehearsal-nos'
            return (
              <div
                key={region.id}
                id={region.id}
                className="region"
                style={{ top: layout.regionTop, height: layout.regionHeight }}
              >
                <div className="seg-wrapper" style={{ top: layout.wrapperTop }}>
                  <div className="seg-under-rule" />
                  <div className="segment" />
                  <img
                    className="seg-delete"
                    src="/images/ex.gif"
                    alt="Delete segment"
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      removeRegion(region.id)
                    }}
                  />
                  <img
                    className="seg-handle"
                    src="/images/slider-right-small.png"
                    alt=""
                    onPointerDown={(e) => {
                      e.stopPropagation()
                      startDrag(e, 'segment', region.id)
                    }}
                    onClick={(e) => {
                      e.stopPropagation()
                    }}
                  />
                </div>
                {layout.showFields ? (
                  <>
                    <TagsInput
                      value={region.tags}
                      tagIsSuggestion={region.tagIsSuggestion}
                      tagList={tagList}
                      suppressBlurRef={suppressTagBlurRef}
                      style={{ bottom: layout.fieldsBottom, display: 'inline' }}
                      inputRef={(el) => {
                        tagInputRefs.current[region.id] = el
                      }}
                      onValueChange={(tags, tagIsSuggestion) =>
                        patchRegion(region.id, { tags, tagIsSuggestion })
                      }
                      onFocusStart={() => {
                        focusedTagsIdRef.current = region.id
                      }}
                      onFocusEnd={() => {
                        focusedTagsIdRef.current = null
                      }}
                      onAfterChange={refreshSuggestions}
                      onTabNext={() => {
                        const nextId = nextTagsRegionId(stateRef.current.regions, region.id)
                        if (nextId) tagInputRefs.current[nextId]?.focus()
                      }}
                      onClearClick={() => handleTagDelete(region.id)}
                    />
                    <img
                      className="tag-delete"
                      src="/images/ex.gif"
                      height={15}
                      alt="Clear part name"
                      style={{ bottom: layout.fieldsBottom + 3, display: 'inline' }}
                      onMouseDown={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        suppressTagBlurRef.current = true
                        handleTagDelete(region.id)
                      }}
                    />
                    <input
                      className={labelClass}
                      maxLength={4}
                      value={region.label}
                      style={{ bottom: layout.fieldsBottom, display: 'inline' }}
                      onChange={(e) =>
                        patchRegion(region.id, {
                          label: e.target.value,
                          labelIsSuggestion: false,
                        })
                      }
                      onBlur={(e) => {
                        focusedLabelIdRef.current = null
                        patchRegion(region.id, {
                          label: e.target.value.trim().split(/\s+/).join(' '),
                          labelIsSuggestion: false,
                        })
                        refreshSuggestions()
                      }}
                      onFocus={() => {
                        focusedLabelIdRef.current = region.id
                        if (region.labelIsSuggestion) {
                          patchRegion(region.id, { label: '', labelIsSuggestion: false })
                        }
                        refreshSuggestions()
                      }}
                      onKeyUp={() => refreshSuggestions()}
                      onClick={(e) => {
                        if ((e.target as HTMLInputElement).value === '(none)') {
                          ;(e.target as HTMLInputElement).select()
                        }
                      }}
                    />
                    <img
                      className="rehearsal-nos-delete"
                      src="/images/ex.gif"
                      height={15}
                      alt=""
                      style={{ bottom: layout.fieldsBottom + 3, display: 'inline' }}
                      onMouseDown={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        handleLabelDelete(region.id)
                      }}
                    />
                  </>
                ) : null}
              </div>
            )
          })}
        </div>

        <div
          id="preview-button"
          className="banner-button"
          onClick={() => void handleContinue()}
          role="button"
          tabIndex={0}
        >
          Separate parts &raquo;
        </div>

        <div id="seg-nav-bar">
          <div id="page-num">
            page {pageNum} of {data.num_pages}
            {saving ? ' (saving…)' : ''}
          </div>
          <div id="prev-page">
            {canGoPrev ? (
              <a
                href="#"
                className="red"
                onClick={(e) => {
                  e.preventDefault()
                  if (pageNum <= previewerStart) {
                    setPreviewerStart((s) => s - 6)
                    void changePage(pageNum - 1)
                  } else {
                    void changePage(pageNum - 1)
                  }
                }}
              >
                &laquo; previous
              </a>
            ) : (
              <span style={navDisabledStyle}>&laquo; previous</span>
            )}
          </div>
          <div id="next-page">
            {canGoNext ? (
              <a
                href="#"
                className="red"
                onClick={(e) => {
                  e.preventDefault()
                  if (pageNum >= previewerStart + 5) {
                    setPreviewerStart((s) => s + 6)
                    void changePage(pageNum + 1)
                  } else {
                    void changePage(pageNum + 1)
                  }
                }}
              >
                next &raquo;
              </a>
            ) : (
              <span style={navDisabledStyle}>next &raquo;</span>
            )}
          </div>
        </div>
      </div>

      {error ? (
        <p className="red" style={{ textAlign: 'center' }}>
          {error}
        </p>
      ) : null}
    </div>
  )
}
