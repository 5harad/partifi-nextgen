import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getCsrfToken, saveAllPageSegments, savePageSegments } from '../../lib/api'
import {
  applySuggestionsToRegions,
  buildTagList,
  nextTagsRegionId,
} from '../../lib/segmentTagSuggestions'
import { TagsInput } from './TagsInput'
import {
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
import { getViewerDimensions, type Orientation } from '../../lib/pageDimensions'
import {
  getSegmentEditorLayout,
  isPageInPreviewWindow,
  lastPageInPreviewWindow,
  maxPreviewerStart,
  minimalPreviewStartForPage,
  nextPreviewerStart,
  prevPreviewerStart,
  segmentEditorCssVars,
} from '../../lib/segmentEditorLayout'
import { useSessionImageCache, type SessionImageRequest } from '../../lib/useSessionImageCache'
import type { PageSegmentData, RegionState, SegmentDataResponse } from '../../types/segment'

type Props = {
  data: SegmentDataResponse
}

function clonePageData(page: PageSegmentData): PageSegmentData {
  return JSON.parse(JSON.stringify(page))
}

export function SegmentEditor({ data }: Props) {
  const navigate = useNavigate()
  const segmenterRef = useRef<HTMLDivElement>(null)
  const sliderRef = useRef<HTMLDivElement>(null)

  const orientation: Orientation = data.orientation ?? 'portrait'
  const { width: viewerWidth, height: viewerHeight } = getViewerDimensions(orientation)
  const segmentLayout = useMemo(() => getSegmentEditorLayout(orientation), [orientation])
  const segmentCssVars = useMemo(
    () => segmentEditorCssVars(segmentLayout),
    [segmentLayout],
  )
  const thumbStride = segmentLayout.thumbStride
  const isLandscape = orientation === 'landscape'

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
  const [thumbTransition, setThumbTransition] = useState(false)
  const [regions, setRegions] = useState<RegionState[]>(() =>
    regionsFromPageData(
      pagesData.p1 ?? { left_margin: 0, right_margin: 100, rotation: 0, segments: [] },
      orientation,
    ),
  )
  const [leftMarginPx, setLeftMarginPx] = useState(() =>
    marginPctToPx(pagesData.p1?.left_margin ?? 0, orientation),
  )
  const [rightMarginPx, setRightMarginPx] = useState(() =>
    marginPctToPx(pagesData.p1?.right_margin ?? 100, orientation),
  )
  const [rotation, setRotation] = useState(pagesData.p1?.rotation ?? 0)
  const serverPageDataRef = useRef<PageSegmentData>(
    clonePageData(pagesData.p1 ?? { left_margin: 0, right_margin: 100, rotation: 0, segments: [] }),
  )
  const serverPagesDataRef = useRef<Record<string, PageSegmentData>>(
    Object.fromEntries(Object.entries(pagesData).map(([key, page]) => [key, clonePageData(page)])),
  )

  const [tagList, setTagList] = useState<string[]>(() => buildTagList(pagesData, data.num_pages))
  const [saving, setSaving] = useState(false)
  const saveInFlightRef = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const focusedLabelIdRef = useRef<string | null>(null)
  const focusedTagsIdRef = useRef<string | null>(null)
  const tagInputRefs = useRef<Record<string, HTMLInputElement | null>>({})
  const suppressTagBlurRef = useRef(false)
  const sessionImageRequests = useMemo<SessionImageRequest[]>(() => {
    const firstPage = 1
    const primary: SessionImageRequest[] = []
    const background: SessionImageRequest[] = []
    for (let page = 1; page <= data.num_pages; page++) {
      const lowresUrl = data.image_urls.lowres[String(page)]
      const thumbUrl = data.image_urls.thumbs[String(page)]
      const requests = [lowresUrl, thumbUrl].flatMap((url) =>
        url ? [{ key: url, url, priority: page === firstPage ? 'high' as const : 'low' as const }] : [],
      )
      if (page === firstPage) primary.push(...requests)
      else background.push(...requests)
    }
    return [...primary, ...background]
  }, [data.image_urls, data.num_pages])
  const sessionImageUrls = useSessionImageCache(sessionImageRequests, data)

  const stateRef = useRef({
    regions,
    leftMarginPx,
    rightMarginPx,
    rotation,
    pageNum,
    previewerStart,
    pagesData,
  })
  useEffect(() => {
    stateRef.current = {
      regions,
      leftMarginPx,
      rightMarginPx,
      rotation,
      pageNum,
      previewerStart,
      pagesData,
    }
  }, [regions, leftMarginPx, rightMarginPx, rotation, pageNum, previewerStart, pagesData])

  useEffect(() => {
    setThumbTransition(false)
    const frame = requestAnimationFrame(() => {
      requestAnimationFrame(() => setThumbTransition(true))
    })
    return () => cancelAnimationFrame(frame)
  }, [orientation])

  const currentPageKey = `p${pageNum}`
  const pageImageUrl = sessionImageUrls[data.image_urls.lowres[String(pageNum)]]
  const layouts = useMemo(() => computeRegionLayouts(regions, orientation), [regions, orientation])

  const leftMargin = Math.min(leftMarginPx, rightMarginPx)
  const rightMargin = Math.max(leftMarginPx, rightMarginPx)
  const leftGrayWidth = Math.min(leftMarginPx, rightMarginPx) + 7
  const rightGrayWidth = viewerWidth - 7 - Math.max(leftMarginPx, rightMarginPx)

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
        marginPxToPct(leftMargin, orientation),
        marginPxToPct(rightMargin, orientation),
        rotation,
        orientation,
      )
      const allPages = { ...stateRef.current.pagesData, [currentPageKey]: pageData }
      return syncWithSuggestions(nextRegions, allPages)
    },
    [currentPageKey, leftMargin, rightMargin, rotation, syncWithSuggestions, orientation],
  )

  const refreshSuggestions = useCallback(() => {
    commitRegions(stateRef.current.regions)
  }, [commitRegions])

  const replaceRegions = useCallback(
    (nextRegions: RegionState[]) => {
      const pageData = buildPageData(
        nextRegions,
        marginPxToPct(leftMargin, orientation),
        marginPxToPct(rightMargin, orientation),
        rotation,
        orientation,
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
    [currentPageKey, leftMargin, rightMargin, rotation, pageNum, data.num_pages, orientation],
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
      marginPxToPct(leftMargin, orientation),
      marginPxToPct(rightMargin, orientation),
      rotation,
      orientation,
    )
  }, [regions, leftMargin, rightMargin, rotation, orientation])

  const persistPage = useCallback(
    async (page: number, pageData: PageSegmentData, csrfToken: string) => {
      await savePageSegments(data.private_id, page, pageData, csrfToken)
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
    serverPageDataRef.current = clonePageData(serverPagesDataRef.current[key] ?? pageData)
    const rawRegions = regionsFromPageData(pageData, orientation)
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
    setLeftMarginPx(marginPctToPx(pageData.left_margin, orientation))
    setRightMarginPx(marginPctToPx(pageData.right_margin, orientation))
    setRotation(pageData.rotation)
    setPageNum(nextPage)
  }

  const changePage = useCallback(
    async (nextPage: number, previewStartOverride?: number) => {
      if (saveInFlightRef.current) return
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
        marginPxToPct(Math.min(leftPx, rightPx), orientation),
        marginPxToPct(Math.max(leftPx, rightPx), orientation),
        rot,
        orientation,
      )
      const key = `p${current}`
      const updatedPages = { ...currentPages, [key]: pageData }
      setPagesData(updatedPages)
      setTagList(buildTagList(updatedPages, data.num_pages))

      let acquiredSaveLock = false
      try {
        if (!pageDataAreEqual(serverPageDataRef.current, pageData)) {
          saveInFlightRef.current = true
          acquiredSaveLock = true
          setSaving(true)
          const token = await getCsrfToken()
          await persistPage(current, pageData, token)
          const savedPageData = clonePageData(pageData)
          serverPageDataRef.current = savedPageData
          serverPagesDataRef.current = {
            ...serverPagesDataRef.current,
            [key]: savedPageData,
          }
        }
        setPreviewerStart(
          previewStartOverride ??
            minimalPreviewStartForPage(
              nextPage,
              stateRef.current.previewerStart,
              data.num_pages,
            ),
        )
        applyPageData(nextPage, updatedPages)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Save failed')
      } finally {
        if (acquiredSaveLock) {
          saveInFlightRef.current = false
          setSaving(false)
        }
      }
    },
    [persistPage, data.num_pages, orientation],
  )

  const scrollPreviewerNext = useCallback(() => {
    if (saveInFlightRef.current) return
    const newStart = nextPreviewerStart(previewerStart, data.num_pages)
    if (newStart === previewerStart) return
    if (isPageInPreviewWindow(pageNum, newStart)) {
      setPreviewerStart(newStart)
      return
    }
    void changePage(newStart, newStart)
  }, [changePage, data.num_pages, pageNum, previewerStart])

  const scrollPreviewerBack = useCallback(() => {
    if (saveInFlightRef.current) return
    const newStart = prevPreviewerStart(previewerStart)
    if (newStart === previewerStart) return
    if (isPageInPreviewWindow(pageNum, newStart)) {
      setPreviewerStart(newStart)
      return
    }
    void changePage(lastPageInPreviewWindow(newStart, data.num_pages), newStart)
  }, [changePage, data.num_pages, pageNum, previewerStart])

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
    if (y <= 1 || y >= viewerHeight - 1 || x <= 0 || x >= viewerWidth) return

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

    let segmentDragMoved = false
    let segmentDragStartY = 0
    let segmentGrabOffsetY = 0
    if (kind === 'segment' && regionId && segmenterRef.current) {
      const rect = segmenterRef.current.getBoundingClientRect()
      segmentDragStartY =
        stateRef.current.regions.find((r) => r.id === regionId)?.topPx ?? 0
      segmentGrabOffsetY = e.clientY - rect.top - segmentDragStartY
    }

    let marginGrabOffsetX = 0
    if (kind === 'left-margin' && segmenterRef.current) {
      const rect = segmenterRef.current.getBoundingClientRect()
      marginGrabOffsetX = e.clientX - rect.left - stateRef.current.leftMarginPx
    } else if (kind === 'right-margin' && segmenterRef.current) {
      const rect = segmenterRef.current.getBoundingClientRect()
      marginGrabOffsetX = e.clientX - rect.left - stateRef.current.rightMarginPx
    }

    let rotationGrabOffset = 0
    if (kind === 'rotation' && sliderRef.current) {
      const sliderRect = sliderRef.current.getBoundingClientRect()
      rotationGrabOffset = e.clientX - sliderRect.left - target.offsetLeft
    }

    const updateRotation = (clientX: number) => {
      if (!sliderRef.current) return
      const rect = sliderRef.current.getBoundingClientRect()
      const left = Math.max(0, Math.min(99, clientX - rect.left - rotationGrabOffset))
      const deg = 10 - left / 5
      setRotation(deg)
      stateRef.current.rotation = deg
    }

    const updateSegmentY = (clientY: number) => {
      if (!regionId || !segmenterRef.current) return
      const rect = segmenterRef.current.getBoundingClientRect()
      const y = Math.max(0, Math.min(viewerHeight, clientY - rect.top - segmentGrabOffsetY))
      if (Math.abs(y - segmentDragStartY) > 3) {
        segmentDragMoved = true
      }
      setRegions((prev) => {
        const clamped = clampSegmentTopPx(y, regionId, prev, orientation)
        const updated = prev.map((r) => (r.id === regionId ? { ...r, topPx: clamped } : r))
        stateRef.current.regions = updated
        return updated
      })
    }

    const updateLeftMargin = (clientX: number) => {
      if (!segmenterRef.current) return
      const rect = segmenterRef.current.getBoundingClientRect()
      const x = Math.max(0, Math.min(viewerWidth, clientX - rect.left - marginGrabOffsetX))
      setLeftMarginPx(x)
      stateRef.current.leftMarginPx = x
    }

    const updateRightMargin = (clientX: number) => {
      if (!segmenterRef.current) return
      const rect = segmenterRef.current.getBoundingClientRect()
      const x = Math.max(0, Math.min(viewerWidth, clientX - rect.left - marginGrabOffsetX))
      setRightMarginPx(x)
      stateRef.current.rightMarginPx = x
    }

    const onMove = (ev: PointerEvent) => {
      if (kind === 'segment') {
        updateSegmentY(ev.clientY)
      } else if (kind === 'left-margin') {
        updateLeftMargin(ev.clientX)
      } else if (kind === 'right-margin') {
        updateRightMargin(ev.clientX)
      } else if (kind === 'rotation') {
        updateRotation(ev.clientX)
      }
    }

    const onUp = () => {
      target.releasePointerCapture(e.pointerId)
      target.removeEventListener('pointermove', onMove)
      target.removeEventListener('pointerup', onUp)

      if (kind === 'segment' && segmentDragMoved && segmenterRef.current) {
        const el = segmenterRef.current
        const blockClick = (ev: MouseEvent) => {
          el.removeEventListener('click', blockClick, true)
          ev.stopPropagation()
          ev.preventDefault()
        }
        el.addEventListener('click', blockClick, true)
      }

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
        marginPxToPct(Math.min(latestLeft, latestRight), orientation),
        marginPxToPct(Math.max(latestLeft, latestRight), orientation),
        latestRotation,
        orientation,
      )
      const allPages = { ...latestPages, [`p${latestPage}`]: pageData }
      syncWithSuggestions(latestRegions, allPages)
    }

    if (kind === 'rotation') {
      updateRotation(e.clientX)
    } else if (kind === 'segment') {
      updateSegmentY(e.clientY)
    } else if (kind === 'left-margin') {
      updateLeftMargin(e.clientX)
    } else if (kind === 'right-margin') {
      updateRightMargin(e.clientX)
    }

    target.addEventListener('pointermove', onMove)
    target.addEventListener('pointerup', onUp)
  }

  const handleContinue = async () => {
    if (saveInFlightRef.current) return
    const currentPages = { ...pagesData, [currentPageKey]: getCurrentPageData() }
    const allPages = materializeAllPagesWithSuggestions(currentPages, data.num_pages, orientation)
    const hasTag = Object.values(allPages).some((page) =>
      page.segments.some((s) => s.tags !== '' && s.tags !== '(none)'),
    )
    if (!hasTag) {
      window.alert('Please label the parts before continuing.')
      return
    }
    try {
      saveInFlightRef.current = true
      setSaving(true)
      setPagesData(allPages)
      setTagList(buildTagList(allPages, data.num_pages))
      const dirtyPages = Object.entries(allPages).filter(
        ([key, page]) => !pageDataAreEqual(serverPagesDataRef.current[key], page),
      )
      if (dirtyPages.length) {
        const token = await getCsrfToken()
        const dirtyPagesByKey = Object.fromEntries(dirtyPages)
        await saveAllPageSegments(data.private_id, dirtyPagesByKey, token)
        serverPagesDataRef.current = {
          ...serverPagesDataRef.current,
          ...Object.fromEntries(dirtyPages.map(([key, page]) => [key, clonePageData(page)])),
        }
        serverPageDataRef.current = clonePageData(allPages[currentPageKey])
      }
      navigate(`/${data.private_id}/preview`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      saveInFlightRef.current = false
      setSaving(false)
    }
  }

  const thumbsOffset = -(previewerStart - 1) * thumbStride
  const canGoPrev = !saving && pageNum > 1
  const canGoNext = !saving && pageNum < data.num_pages
  const canScrollPreviewerNext = previewerStart < maxPreviewerStart(data.num_pages)
  const canScrollPreviewerBack = previewerStart > 1
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
      <div
        id="segment-header"
        className={isLandscape ? 'orientation-landscape' : undefined}
        style={segmentCssVars}
      >
        STEP 2. &nbsp; Label each part for separation
      </div>
      <div
        id="segment-panel"
        className={isLandscape ? 'orientation-landscape' : undefined}
        style={{ ...segmentCssVars, pointerEvents: saving ? 'none' : undefined }}
        inert={saving}
      >
        <div id="previewer">
          <div
            id="thumbs"
            className={thumbTransition ? 'thumbs-animated' : undefined}
            style={{ left: thumbsOffset }}
          >
            {Array.from({ length: data.num_pages }, (_, i) => {
              const n = i + 1
              const active = n === pageNum
              return (
                <div
                  key={n}
                  className="thumb"
                  id={`preview-${n}`}
                  style={{
                    left: (n - 1) * thumbStride,
                    color: active ? '#E00000' : 'black',
                    cursor: saving ? 'default' : 'pointer',
                  }}
                  onClick={() => void changePage(n)}
                  role="button"
                  tabIndex={saving ? -1 : 0}
                  aria-disabled={saving}
                  onKeyDown={(ev) => {
                    if (ev.key === 'Enter' || ev.key === ' ') void changePage(n)
                  }}
                >
                  page {n}
                  <br />
                  <div className="img-frame" style={{ borderColor: active ? '#E00000' : '#D8D8C2' }}>
                    {sessionImageUrls[data.image_urls.thumbs[String(n)]] ? (
                      <img
                        src={sessionImageUrls[data.image_urls.thumbs[String(n)]]}
                        alt={`Page ${n}`}
                      />
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {canScrollPreviewerNext ? (
          <div
            id="previewer-next"
            className="next-button"
            onClick={scrollPreviewerNext}
            role="button"
            tabIndex={saving ? -1 : 0}
            aria-disabled={saving}
            style={saving ? navDisabledStyle : undefined}
          >
            &raquo;
          </div>
        ) : null}

        {canScrollPreviewerBack ? (
          <div
            id="previewer-back"
            className="next-button"
            onClick={scrollPreviewerBack}
            role="button"
            tabIndex={saving ? -1 : 0}
            aria-disabled={saving}
            style={saving ? navDisabledStyle : undefined}
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
          {pageImageUrl ? (
            <img
              src={pageImageUrl}
              width={viewerWidth}
              height={viewerHeight}
              alt={`Score page ${pageNum}`}
              style={{ transform: `rotate(${-rotation}deg)` }}
            />
          ) : null}
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
          tabIndex={saving ? -1 : 0}
          aria-disabled={saving}
          style={saving ? navDisabledStyle : undefined}
        >
          Separate parts &raquo;
        </div>

        <div id="seg-nav-bar">
          <div id="seg-nav-row">
            <div id="prev-page">
              {canGoPrev ? (
                <a
                  href="#"
                  className="red"
                  onClick={(e) => {
                    e.preventDefault()
                    void changePage(pageNum - 1)
                  }}
                >
                  &laquo; previous
                </a>
              ) : (
                <span style={navDisabledStyle}>&laquo; previous</span>
              )}
            </div>
            <div id="page-num">
              page {pageNum} of {data.num_pages}
              {saving ? ' (saving…)' : ''}
            </div>
            <div id="next-page">
              {canGoNext ? (
                <a
                  href="#"
                  className="red"
                  onClick={(e) => {
                    e.preventDefault()
                    void changePage(pageNum + 1)
                  }}
                >
                  next &raquo;
                </a>
              ) : (
                <span style={navDisabledStyle}>next &raquo;</span>
              )}
            </div>
          </div>
          <p id="orientation-hint">
            Page sideways or upside down?{' '}
            <Link className="red" to={`/${data.private_id}/orientation`}>
              Fix page orientation
            </Link>
          </p>
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
