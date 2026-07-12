import {
  getDimensions,
  type Orientation,
} from './pageDimensions'

const SLIDER_RANGE = 46

/** Default line spacing for new parts (matches legacy DB default). */
export const DEFAULT_SPACING = 0.1

/** Matches legacy jQuery UI snapTolerance on the spacing sliders. */
export const SLIDER_SNAP_TOLERANCE = 2

export function spacingToSliderUpTop(spacing: number): number {
  return Math.round(SLIDER_RANGE - spacing * 40)
}

export const DEFAULT_SLIDER_UP_TOP = spacingToSliderUpTop(DEFAULT_SPACING)

export function sliderUpTopToSpacing(top: number): number {
  return (SLIDER_RANGE - top) / 40
}

export function applySliderSnap(top: number): number {
  if (Math.abs(top - DEFAULT_SLIDER_UP_TOP) <= SLIDER_SNAP_TOLERANCE) {
    return DEFAULT_SLIDER_UP_TOP
  }
  return top
}

export function abbreviate(str: string): string {
  return str
    .split(' ')
    .map((token) => {
      if (token.length <= 3) return token
      const condensed = token
        .split('')
        .map((chr, ndx) => (ndx === 0 || !'aeiou'.includes(chr) ? chr : ''))
        .join('')
      return condensed.slice(0, 3)
    })
    .join(' ')
}

function previewScale(orientation: Orientation): number {
  const dims = getDimensions(orientation)
  return dims.previewPaneWidth / dims.highresWidth
}

export function lowresHeight(highresPx: number, orientation: Orientation = 'portrait'): number {
  return Math.round(highresPx * previewScale(orientation))
}

export function lowresWidth(highresPx: number, orientation: Orientation = 'portrait'): number {
  return Math.round(highresPx * previewScale(orientation))
}

export function spacingLowres(spacing: number, orientation: Orientation = 'portrait'): number {
  return Math.round(spacingHighres(spacing) * previewScale(orientation))
}

export function spacingHighres(spacing: number): number {
  return Math.round(spacing * 300)
}

export function computeCues(partName: string, partSegments: Record<string, number[]>): Set<number> {
  const cueSegs: number[] = []
  const nonCueSegs: number[] = []
  for (const piece of partName.split(' + ')) {
    if (piece.endsWith(' cue')) {
      cueSegs.push(...(partSegments[piece] ?? []))
    } else {
      nonCueSegs.push(...(partSegments[piece] ?? []))
    }
  }
  return new Set(cueSegs.filter((seg) => !nonCueSegs.includes(seg)))
}

export function pageChunks(
  segments: number[],
  heights: number[],
  spacingHighresPx: number,
  breaks: number[],
  orientation: Orientation = 'portrait',
): number[][] {
  const pageChunkMax = getDimensions(orientation).pageChunkMax
  const chunks: number[][] = []
  let start = 0
  let h = 0
  for (let i = 0; i < segments.length; i++) {
    const segId = segments[i]
    const segH = heights[segId]
    if (h + segH > pageChunkMax || breaks.includes(i - 1)) {
      if (start < i) {
        chunks.push(segments.slice(start, i))
      }
      start = i
      h = 0
    }
    h += segH + spacingHighresPx
  }
  chunks.push(segments.slice(start))
  return chunks
}

export function uniqueSorted(arr: number[]): number[] {
  return [...new Set(arr)].sort((a, b) => a - b)
}
