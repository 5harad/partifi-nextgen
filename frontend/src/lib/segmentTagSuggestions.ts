import type { PageSegmentData, RegionState } from '../types/segment'
import {
  BASE_TAGS,
  isConfirmedLabel,
  isPartChainAnchor,
  needsLabelSuggestion,
  needsPartSuggestion,
  splitTags,
  uniqueTags,
} from './segmentTags'

export type TagEntry = {
  page: number
  pos: [number, number]
  tags: string
  tagIsSuggestion: boolean
  label: string
  labelIsSuggestion: boolean
}

export function getAllTagEntries(
  pagesData: Record<string, PageSegmentData>,
  numPages: number,
): TagEntry[] {
  const tags: TagEntry[] = []
  for (let page = 1; page <= numPages; page++) {
    const pageData = pagesData[`p${page}`]
    if (!pageData) continue
    for (const seg of pageData.segments) {
      tags.push({
        page,
        pos: seg.pos,
        tags: seg.tags,
        tagIsSuggestion: seg.tag_is_suggestion,
        label: seg.label,
        labelIsSuggestion: seg.label_is_suggestion,
      })
    }
  }
  return tags
}

export function buildTagList(pagesData: Record<string, PageSegmentData>, numPages: number): string[] {
  const tagCount: Record<string, number> = {}
  for (const tag of BASE_TAGS) tagCount[tag] = 0

  for (const entry of getAllTagEntries(pagesData, numPages)) {
    for (const term of splitTags(entry.tags)) {
      if (term in tagCount) {
        tagCount[term] += 1
      } else if (term !== '' && term !== '(none)') {
        tagCount[term] = 1
      }
    }
  }

  return Object.keys(tagCount).sort((a, b) => {
    if (tagCount[a] !== tagCount[b]) return tagCount[b] - tagCount[a]
    return a.localeCompare(b)
  })
}

export function extractLast(value: string): string {
  const terms = splitTags(value)
  return terms[terms.length - 1] ?? ''
}

export function filterTagAutocomplete(tagList: string[], term: string): string[] {
  if (!term) return []
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const matcher = new RegExp(escaped, 'i')
  return tagList.filter((value) => matcher.test(value))
}

function genSystemSuggestions(tags: string[], start: number, end?: number): number[] | false {
  const endIdx = end ?? tags.length - 1
  if (start >= endIdx) return false
  const slice = tags.length > endIdx + 1 ? tags.slice(0, endIdx + 1) : tags

  const patternEnd = slice.indexOf(slice[start], start + 1)
  if (patternEnd === -1) return false
  const pattern = slice.slice(start, patternEnd)
  if (pattern.length !== uniqueTags(pattern).length) return false

  const systemStarts: number[] = []
  let ndx = start
  while (ndx <= endIdx && slice[ndx] === pattern[(ndx - start) % pattern.length]) {
    if (slice[ndx] === pattern[0]) systemStarts.push(ndx)
    ndx += 1
  }

  if (ndx > endIdx && (ndx - start) % pattern.length === 0) {
    return systemStarts
  }
  if ((ndx - start) % pattern.length !== 0) {
    const popped = systemStarts.pop()
    if (popped === undefined) return false
    const next = genSystemSuggestions(slice, popped, endIdx)
    return next ? systemStarts.concat(next) : false
  }
  const nextA = genSystemSuggestions(slice, ndx, endIdx)
  if (nextA) return systemStarts.concat(nextA)
  const popped = systemStarts.pop()
  if (popped === undefined) return false
  const nextB = genSystemSuggestions(slice, popped, endIdx)
  return nextB ? systemStarts.concat(nextB) : false
}

export function computePartAndLabelSuggestions(
  pagesData: Record<string, PageSegmentData>,
  numPages: number,
  pageNum: number,
): { partSuggestions: string[]; labelSuggestions: string[]; pageStart: number } {
  const tags = getAllTagEntries(pagesData, numPages)
  tags.sort((a, b) => (a.page !== b.page ? a.page - b.page : a.pos[0] - b.pos[0]))

  const nextTag: Record<string, string> = {}
  const pageStart: number[] = []
  const partSuggestions: string[] = []
  let page = 0

  tags.forEach((val, ndx) => {
    if (val.page > pageNum) return

    if (page !== val.page) {
      page = val.page
      pageStart[page] = ndx
    }

    if (isPartChainAnchor(val.tags, val.tagIsSuggestion)) {
      partSuggestions[ndx] = val.tags
    } else if (ndx > 0 && partSuggestions[ndx - 1] in nextTag) {
      partSuggestions[ndx] = nextTag[partSuggestions[ndx - 1]]
    } else if (ndx > pageStart[page]) {
      partSuggestions[ndx] = partSuggestions[pageStart[page]]
    } else {
      partSuggestions[ndx] = ''
    }

    if (ndx > 0 && partSuggestions[ndx - 1] !== '' && partSuggestions[ndx] !== '') {
      nextTag[partSuggestions[ndx - 1]] = partSuggestions[ndx]
    }
  })

  let start = pageStart[Math.max(1, pageNum - 1)] ?? 0
  while (partSuggestions[start] === '') start += 1

  const systemStarts = genSystemSuggestions(partSuggestions, start)
  const labelSuggestions: string[] = new Array(partSuggestions.length).fill('')

  if (systemStarts) {
    const starts = [...systemStarts, partSuggestions.length]
    for (let i = 0; i < starts.length - 1; i++) {
      const markers: string[] = []
      for (let j = starts[i]; j < starts[i + 1]; j++) {
        const entry = tags[j]
        if (entry && isConfirmedLabel(entry.label, entry.labelIsSuggestion)) {
          markers.push(entry.label)
        }
      }
      const uniqueMarkers = uniqueTags(markers)
      if (uniqueMarkers.length === 1) {
        for (let j = starts[i]; j < starts[i + 1]; j++) {
          labelSuggestions[j] = uniqueMarkers[0]
        }
      }
    }
  }

  return {
    partSuggestions,
    labelSuggestions,
    pageStart: pageStart[pageNum] ?? 0,
  }
}

export function applySuggestionsToRegions(
  regions: RegionState[],
  pagesData: Record<string, PageSegmentData>,
  pageNum: number,
  numPages: number,
  focusedLabelId: string | null,
  focusedTagsId: string | null = null,
): RegionState[] {
  const sorted = [...regions].sort((a, b) => a.topPx - b.topPx)
  const fieldRegions = sorted.slice(0, -1)
  if (fieldRegions.length === 0) return regions

  const { partSuggestions, labelSuggestions, pageStart } = computePartAndLabelSuggestions(
    pagesData,
    numPages,
    pageNum,
  )

  return regions.map((region) => {
    const idx = fieldRegions.findIndex((r) => r.id === region.id)
    if (idx < 0) return region

    const globalIdx = pageStart + idx
    const tagSugg = partSuggestions[globalIdx] ?? ''
    const labelSugg = labelSuggestions[globalIdx] ?? ''
    const next = { ...region }

    if (
      region.id !== focusedTagsId &&
      needsPartSuggestion(region.tags, region.tagIsSuggestion)
    ) {
      next.tags = tagSugg
      next.tagIsSuggestion = tagSugg !== ''
    }
    if (
      region.id !== focusedLabelId &&
      needsLabelSuggestion(region.label, region.labelIsSuggestion)
    ) {
      next.label = labelSugg
      next.labelIsSuggestion = labelSugg !== ''
    }
    return next
  })
}

export function nextTagsRegionId(regions: RegionState[], currentId: string): string | null {
  const sorted = [...regions].sort((a, b) => a.topPx - b.topPx)
  const fieldRegions = sorted.slice(0, -1)
  const currentIdx = fieldRegions.findIndex((r) => r.id === currentId)
  if (currentIdx < 0 || currentIdx >= fieldRegions.length - 1) return null
  return fieldRegions[currentIdx + 1].id
}

export function applyTagSelection(current: string, selected: string): string {
  const terms = splitTags(current)
  terms.pop()
  terms.push(selected)
  terms.push('')
  return terms.join(', ')
}
