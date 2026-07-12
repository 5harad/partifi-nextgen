export type Orientation = 'portrait' | 'landscape'

export type PageDimensions = {
  orientation: Orientation
  highresWidth: number
  highresHeight: number
  lowresWidth: number
  lowresHeight: number
  thumbWidth: number
  thumbHeight: number
  previewPaneWidth: number
  pageChunkMax: number
}

export const PORTRAIT: PageDimensions = {
  orientation: 'portrait',
  highresWidth: 2550,
  highresHeight: 3300,
  lowresWidth: 600,
  lowresHeight: 776,
  thumbWidth: 100,
  thumbHeight: 129,
  previewPaneWidth: 367,
  pageChunkMax: 2865,
}

export const LANDSCAPE: PageDimensions = {
  orientation: 'landscape',
  highresWidth: 3300,
  highresHeight: 2550,
  lowresWidth: 776,
  lowresHeight: 600,
  thumbWidth: 129,
  thumbHeight: 100,
  previewPaneWidth: 475,
  pageChunkMax: 1925,
}

export function getDimensions(orientation: Orientation): PageDimensions {
  return orientation === 'landscape' ? LANDSCAPE : PORTRAIT
}

export function getViewerDimensions(orientation: Orientation): {
  width: number
  height: number
} {
  const dims = getDimensions(orientation)
  return { width: dims.lowresWidth, height: dims.lowresHeight }
}

/** Gap between stacked preview pages in the horizontal pager (pane width + 13px). */
export function getPreviewPageStride(orientation: Orientation): number {
  return getDimensions(orientation).previewPaneWidth + 13
}

/** Width of page-break / proposed-break markers inside the preview part column. */
export function getPageBreakMarkerWidth(orientation: Orientation): number {
  return getDimensions(orientation).previewPaneWidth - 27
}

/** Horizontal stride between page thumbnails in the segment editor strip. */
export function getThumbStride(orientation: Orientation): number {
  const dims = getDimensions(orientation)
  return dims.thumbWidth + 20
}
