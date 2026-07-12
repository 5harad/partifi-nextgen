import type { Orientation } from './pageDimensions'
import { getViewerDimensions } from './pageDimensions'
import type { PageSegmentData, RegionState, SegmentItem } from '../types/segment'
import { applySuggestionsToRegions } from './segmentTagSuggestions'

/** @deprecated Use getViewerDimensions(orientation) — portrait defaults for legacy callers. */
export const VIEWER_HEIGHT = 776
/** @deprecated Use getViewerDimensions(orientation) — portrait defaults for legacy callers. */
export const VIEWER_WIDTH = 600

/** Minimum px between segment divider lines (matches legacy region padding). */
export const MIN_SEGMENT_GAP = 11

export function pctToPx(pct: number, orientation: Orientation = 'portrait'): number {
  const { height } = getViewerDimensions(orientation)
  return Math.round((pct / 100) * height)
}

export function pxToPct(px: number, orientation: Orientation = 'portrait'): number {
  const { height } = getViewerDimensions(orientation)
  return Math.round((px / height) * 1000) / 10
}

export function pageDataAreEqual(a: PageSegmentData, b: PageSegmentData): boolean {
  if (
    a.left_margin !== b.left_margin ||
    a.right_margin !== b.right_margin ||
    a.rotation !== b.rotation ||
    a.segments.length !== b.segments.length
  ) {
    return false
  }
  for (let i = 0; i < a.segments.length; i++) {
    const sa = a.segments[i]
    const sb = b.segments[i]
    if (
      sa.label !== sb.label ||
      sa.tags !== sb.tags ||
      sa.label_is_suggestion !== sb.label_is_suggestion ||
      sa.tag_is_suggestion !== sb.tag_is_suggestion ||
      sa.pos[0] !== sb.pos[0] ||
      sa.pos[1] !== sb.pos[1]
    ) {
      return false
    }
  }
  return true
}

export function buildPageData(
  regions: RegionState[],
  leftMarginPct: number,
  rightMarginPct: number,
  rotation: number,
  orientation: Orientation = 'portrait',
): PageSegmentData {
  const sorted = [...regions].sort((a, b) => a.topPx - b.topPx)
  const segments: SegmentItem[] = []

  if (sorted.length >= 2) {
    for (let i = 0; i < sorted.length - 1; i++) {
      const top = pxToPct(sorted[i].topPx, orientation)
      const bottom = pxToPct(sorted[i + 1].topPx, orientation)
      segments.push({
        pos: [top, bottom],
        tags: splitTagsForSave(sorted[i].tags),
        tag_is_suggestion: sorted[i].tagIsSuggestion,
        label: sorted[i].label.trim().split(/\s+/).join(' '),
        label_is_suggestion: sorted[i].labelIsSuggestion,
      })
    }
  }

  return {
    left_margin: leftMarginPct,
    right_margin: rightMarginPct,
    rotation,
    segments,
  }
}

function splitTagsForSave(value: string): string {
  return value
    .split(/,\s*/)
    .map((t) => t.trim().split(/\s+/).join(' '))
    .filter(Boolean)
    .join(', ')
}

export type RegionLayout = {
  regionTop: number
  regionHeight: number
  wrapperTop: number
  showFields: boolean
  fieldsBottom: number
}

export function computeRegionLayouts(
  regions: RegionState[],
  orientation: Orientation = 'portrait',
): Map<string, RegionLayout> {
  const { height: viewerHeight } = getViewerDimensions(orientation)
  const sorted = [...regions].sort((a, b) => a.topPx - b.topPx)
  const layouts = new Map<string, RegionLayout>()
  const bottomBound = viewerHeight + 10

  sorted.forEach((region, i) => {
    const segPos = region.topPx
    const top = i === 0 ? -12 : sorted[i - 1].topPx + 10
    const bottom = i === sorted.length - 1 ? bottomBound : sorted[i + 1].topPx - 11
    const showFields = i < sorted.length - 1
    layouts.set(region.id, {
      regionTop: top,
      regionHeight: bottom - top + 1,
      wrapperTop: segPos - top - 11,
      showFields,
      fieldsBottom: showFields ? (bottom - segPos) / 2 - 17 : 0,
    })
  })

  return layouts
}

export function clampSegmentTopPx(
  topPx: number,
  regionId: string,
  regions: RegionState[],
  orientation: Orientation = 'portrait',
): number {
  const { height: viewerHeight } = getViewerDimensions(orientation)
  const sorted = [...regions].sort((a, b) => a.topPx - b.topPx)
  const idx = sorted.findIndex((r) => r.id === regionId)
  if (idx < 0) return topPx

  let minY = 2
  let maxY = viewerHeight - 1
  if (idx > 0) {
    minY = sorted[idx - 1].topPx + MIN_SEGMENT_GAP
  }
  if (idx < sorted.length - 1) {
    maxY = sorted[idx + 1].topPx - MIN_SEGMENT_GAP
  }
  return Math.max(minY, Math.min(maxY, topPx))
}

export function minDistanceToSegments(topPx: number, regions: RegionState[]): number {
  if (regions.length === 0) return 1000
  return Math.min(...regions.map((r) => Math.abs(r.topPx - topPx)))
}

export function marginPxToPct(px: number, orientation: Orientation = 'portrait'): number {
  const { width } = getViewerDimensions(orientation)
  return Math.round((px / width) * 1000) / 10
}

export function marginPctToPx(pct: number, orientation: Orientation = 'portrait'): number {
  const { width } = getViewerDimensions(orientation)
  return Math.round((pct / 100) * width)
}

let regionCounter = 0

export function nextRegionId() {
  regionCounter += 1
  return `region-${regionCounter}`
}

export function regionsFromPageData(
  data: PageSegmentData,
  orientation: Orientation = 'portrait',
): RegionState[] {
  const regions: RegionState[] = []
  for (const seg of data.segments) {
    regions.push({
      id: nextRegionId(),
      topPx: pctToPx(seg.pos[0], orientation),
      tags: seg.tags,
      tagIsSuggestion: seg.tag_is_suggestion,
      label: seg.label,
      labelIsSuggestion: seg.label_is_suggestion,
    })
  }
  if (data.segments.length > 0) {
    const last = data.segments[data.segments.length - 1]
    regions.push({
      id: nextRegionId(),
      topPx: pctToPx(last.pos[1], orientation),
      tags: '',
      tagIsSuggestion: false,
      label: '',
      labelIsSuggestion: false,
    })
  }
  return regions
}

export function materializeAllPagesWithSuggestions(
  pagesData: Record<string, PageSegmentData>,
  numPages: number,
  orientation: Orientation = 'portrait',
): Record<string, PageSegmentData> {
  let allPages = { ...pagesData }
  for (let page = 1; page <= numPages; page++) {
    const key = `p${page}`
    const base = allPages[key] ?? {
      left_margin: 0,
      right_margin: 100,
      rotation: 0,
      segments: [],
    }
    const regions = regionsFromPageData(base, orientation)
    const suggested = applySuggestionsToRegions(
      regions,
      allPages,
      page,
      numPages,
      null,
      null,
    )
    allPages = {
      ...allPages,
      [key]: buildPageData(
        suggested,
        base.left_margin,
        base.right_margin,
        base.rotation,
        orientation,
      ),
    }
  }
  return allPages
}
