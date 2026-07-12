import { getDimensions, getThumbStride, getViewerDimensions, type Orientation } from './pageDimensions'

/** Legacy segment editor chrome — shared with portrait CSS. */
const SEGMENTER_LEFT = 100
const VIEWER_LEFT = 101
const VIEWER_TOP = 222
const LABELS_GAP = 30
const LABELS_COLUMN_WIDTH = 155
const ROTATOR_WIDTH_PAD = 10
const TAG_FIELD_OFFSET = 165
const SEG_UNDER_RULE_ALIGN = 100
const SEG_UNDER_RULE_TAIL_PORTRAIT = 50
const SEG_UNDER_RULE_TAIL_LANDSCAPE = 50
const PANEL_BELOW_VIEWER = 102
const SEG_HANDLE_INSET = 20
const SEG_DELETE_INSET = 40
const ROTATION_LABEL_OFFSET = 180
const ROTATION_SLIDER_OFFSET = 300
const ROTATION_GROUP_WIDTH = ROTATION_SLIDER_OFFSET + 124 - ROTATION_LABEL_OFFSET
const PREVIEWER_LEFT = 100
export const THUMBS_PER_PAGE = 6
const PREVIEWER_NEXT_GAP = 15

/** Leftmost thumb index when the last page is flush to the right edge of the previewer. */
export function maxPreviewerStart(numPages: number): number {
  return Math.max(1, numPages - THUMBS_PER_PAGE + 1)
}

/** Minimal carousel shift so `targetPage` is visible (0 if already visible, else ±1). */
export function minimalPreviewStartForPage(
  targetPage: number,
  previewerStart: number,
  numPages: number,
): number {
  if (isPageInPreviewWindow(targetPage, previewerStart)) {
    return previewerStart
  }
  if (targetPage < previewerStart) {
    return Math.max(1, previewerStart - 1)
  }
  return Math.min(previewerStart + 1, maxPreviewerStart(numPages))
}

export function isPageInPreviewWindow(pageNum: number, previewerStart: number): boolean {
  return pageNum >= previewerStart && pageNum <= previewerStart + THUMBS_PER_PAGE - 1
}

export function nextPreviewerStart(previewerStart: number, numPages: number): number {
  return Math.min(previewerStart + THUMBS_PER_PAGE, maxPreviewerStart(numPages))
}

export function prevPreviewerStart(previewerStart: number): number {
  return Math.max(1, previewerStart - THUMBS_PER_PAGE)
}

export function lastPageInPreviewWindow(previewerStart: number, numPages: number): number {
  return Math.min(previewerStart + THUMBS_PER_PAGE - 1, numPages)
}

export type SegmentEditorLayout = {
  panelWidth: number
  panelHeight: number
  viewerWidth: number
  viewerHeight: number
  rotatorWidth: number
  rotatorLeft: number
  sliderLabelLeft: number
  sliderLeft: number
  segNavTop: number
  segNavWidth: number
  previewButtonTop: number
  previewButtonLeft: number
  previewerWidth: number
  previewerNextLeft: number
  labelsTitleLeft: number
  titleRowBottom: number
  thumbWidth: number
  thumbHeight: number
  thumbStride: number
  segUnderRuleWidth: number
  segDeleteLeft: number
  segHandleLeft: number
  tagsLeft: number
  tagDeleteLeft: number
}

export function getSegmentEditorLayout(orientation: Orientation): SegmentEditorLayout {
  const dims = getDimensions(orientation)
  const { width: viewerWidth, height: viewerHeight } = getViewerDimensions(orientation)

  const panelWidth = SEGMENTER_LEFT + viewerWidth + LABELS_GAP + LABELS_COLUMN_WIDTH
  const panelHeight = VIEWER_TOP + viewerHeight + PANEL_BELOW_VIEWER
  const rotatorWidth = viewerWidth + ROTATOR_WIDTH_PAD
  const rotatorLeft = VIEWER_LEFT - (rotatorWidth - viewerWidth) / 2
  const rotationGroupStart = (rotatorWidth - ROTATION_GROUP_WIDTH) / 2
  const titleRowBottom = panelHeight - 192
  const segUnderRuleTail =
    orientation === 'landscape' ? SEG_UNDER_RULE_TAIL_LANDSCAPE : SEG_UNDER_RULE_TAIL_PORTRAIT
  const thumbStride = getThumbStride(orientation)
  const thumbWidth = dims.thumbWidth + 2
  const previewerWidth = (THUMBS_PER_PAGE - 1) * thumbStride + thumbWidth

  return {
    panelWidth,
    panelHeight,
    viewerWidth,
    viewerHeight,
    rotatorWidth,
    rotatorLeft,
    sliderLabelLeft: rotationGroupStart,
    sliderLeft: rotationGroupStart + (ROTATION_SLIDER_OFFSET - ROTATION_LABEL_OFFSET),
    segNavTop: VIEWER_TOP + viewerHeight + 2,
    segNavWidth: viewerWidth + 2,
    previewButtonTop: VIEWER_TOP + viewerHeight + 52,
    previewButtonLeft: panelWidth - 170,
    previewerWidth,
    previewerNextLeft: PREVIEWER_LEFT + previewerWidth + PREVIEWER_NEXT_GAP,
    labelsTitleLeft: SEGMENTER_LEFT + viewerWidth + LABELS_GAP,
    titleRowBottom,
    thumbWidth,
    thumbHeight: dims.thumbHeight,
    thumbStride,
    segUnderRuleWidth: SEG_UNDER_RULE_ALIGN + viewerWidth + TAG_FIELD_OFFSET + segUnderRuleTail,
    segDeleteLeft: viewerWidth - SEG_DELETE_INSET,
    segHandleLeft: viewerWidth - SEG_HANDLE_INSET,
    tagsLeft: viewerWidth + LABELS_GAP,
    tagDeleteLeft: viewerWidth + TAG_FIELD_OFFSET,
  }
}

export function segmentEditorCssVars(
  layout: SegmentEditorLayout,
): Record<string, string> {
  return {
    '--segment-panel-width': `${layout.panelWidth}px`,
    '--segment-panel-height': `${layout.panelHeight}px`,
    '--viewer-width': `${layout.viewerWidth}px`,
    '--viewer-height': `${layout.viewerHeight}px`,
    '--rotator-width': `${layout.rotatorWidth}px`,
    '--rotator-left': `${layout.rotatorLeft}px`,
    '--slider-label-left': `${layout.sliderLabelLeft}px`,
    '--slider-left': `${layout.sliderLeft}px`,
    '--seg-nav-top': `${layout.segNavTop}px`,
    '--seg-nav-width': `${layout.segNavWidth}px`,
    '--preview-button-top': `${layout.previewButtonTop}px`,
    '--preview-button-left': `${layout.previewButtonLeft}px`,
    '--previewer-width': `${layout.previewerWidth}px`,
    '--previewer-next-left': `${layout.previewerNextLeft}px`,
    '--labels-title-left': `${layout.labelsTitleLeft}px`,
    '--title-row-bottom': `${layout.titleRowBottom}px`,
    '--thumb-width': `${layout.thumbWidth}px`,
    '--thumb-img-width': `${layout.thumbWidth - 2}px`,
    '--thumb-img-height': `${layout.thumbHeight}px`,
    '--seg-under-rule-width': `${layout.segUnderRuleWidth}px`,
    '--seg-delete-left': `${layout.segDeleteLeft}px`,
    '--seg-handle-left': `${layout.segHandleLeft}px`,
    '--tags-left': `${layout.tagsLeft}px`,
    '--tag-delete-left': `${layout.tagDeleteLeft}px`,
  }
}
