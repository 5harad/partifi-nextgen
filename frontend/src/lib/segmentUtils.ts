import type { PageSegmentData, RegionState, SegmentItem } from '../types/segment'
import { applySuggestionsToRegions } from './segmentTagSuggestions'

export const VIEWER_HEIGHT = 776
export const VIEWER_WIDTH = 600

export function pctToPx(pct: number): number {
  return Math.round((pct / 100) * VIEWER_HEIGHT)
}

export function pxToPct(px: number): number {
  return Math.round((px / VIEWER_HEIGHT) * 1000) / 10
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
): PageSegmentData {
  const sorted = [...regions].sort((a, b) => a.topPx - b.topPx)
  const segments: SegmentItem[] = []

  if (sorted.length >= 2) {
    for (let i = 0; i < sorted.length - 1; i++) {
      const top = pxToPct(sorted[i].topPx)
      const bottom = pxToPct(sorted[i + 1].topPx)
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

export function computeRegionLayouts(regions: RegionState[]): Map<string, RegionLayout> {
  const sorted = [...regions].sort((a, b) => a.topPx - b.topPx)
  const layouts = new Map<string, RegionLayout>()

  sorted.forEach((region, i) => {
    const segPos = region.topPx
    const top = i === 0 ? -12 : sorted[i - 1].topPx + 10
    const bottom = i === sorted.length - 1 ? 786 : sorted[i + 1].topPx - 11
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

export function marginPxToPct(px: number): number {
  return Math.round((px / VIEWER_WIDTH) * 1000) / 10
}

export function marginPctToPx(pct: number): number {
  return Math.round((pct / 100) * VIEWER_WIDTH)
}

let regionCounter = 0

export function nextRegionId() {
  regionCounter += 1
  return `region-${regionCounter}`
}

export function regionsFromPageData(data: PageSegmentData): RegionState[] {
  const regions: RegionState[] = []
  for (const seg of data.segments) {
    regions.push({
      id: nextRegionId(),
      topPx: pctToPx(seg.pos[0]),
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
      topPx: pctToPx(last.pos[1]),
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
    const regions = regionsFromPageData(base)
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
      ),
    }
  }
  return allPages
}
