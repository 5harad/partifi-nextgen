import { getDimensions, type Orientation } from './pageDimensions'

/** Mirrors pipeline/paste_segments.py header/footer geometry. */
const FOOTER_BAND_IN = 0.25
const CONTENT_START_OFFSET = 0.7
const HEADER_LEFT_IN = 0.75
const HEADER_RIGHT_IN = 0.75
const HEADER_FONT_PT = 11
const LOGO_PT = 24
const TEXT_INDENT_PT = 28
const PT_PER_IN = 72

const PAGE_SIZES_IN: Record<'letter' | 'a4', [number, number]> = {
  letter: [8.5, 11],
  a4: [8.27, 11.69],
}

function pageDimsInches(pagesize: 'letter' | 'a4', orientation: Orientation): [number, number] {
  const [width, height] = PAGE_SIZES_IN[pagesize]
  if (orientation === 'landscape') {
    return [height, width]
  }
  return [width, height]
}

function verticalLayout(pageH: number, orientation: Orientation): [number, number] {
  if (orientation === 'landscape') {
    return [0.4, pageH - 0.5]
  }
  const bottomMargin = (pageH - 10.5) / 2
  return [bottomMargin, bottomMargin + 10.5]
}

function pasteContentHeightIn(pagesize: 'letter' | 'a4', orientation: Orientation): number {
  const [, pageH] = pageDimsInches(pagesize, orientation)
  const [bottomMargin, topMargin] = verticalLayout(pageH, orientation)
  const contentTop = topMargin - CONTENT_START_OFFSET
  const contentBottom = bottomMargin + FOOTER_BAND_IN
  return contentTop - contentBottom
}

export type PreviewPageLayout = {
  pageWidth: number
  pageHeight: number
  logoTop: number
  logoLeft: number
  logoSize: number
  titleTop: number
  composerTop: number
  partNameTop: number
  linkTop: number
  ruleTop: number
  contentTop: number
  contentHeight: number
  contentPaddingTop: number
  contentPaddingBottom: number
  headerLeft: number
  headerRight: number
  textLeft: number
  fontSize: number
  pageNumberBottom: number
}

function scaleIn(
  inches: number,
  pageWidthIn: number,
  previewPaneWidth: number,
): number {
  return Math.round((inches / pageWidthIn) * previewPaneWidth)
}

function scalePt(
  points: number,
  pageWidthIn: number,
  previewPaneWidth: number,
): number {
  return scaleIn(points / PT_PER_IN, pageWidthIn, previewPaneWidth)
}

/** Layout for one preview page card — letter page size, A4-limited content height. */
export function getPreviewPageLayout(orientation: Orientation): PreviewPageLayout {
  const dims = getDimensions(orientation)
  const [pageWidthIn, pageHIn] = pageDimsInches('letter', orientation)
  const [bottomMargin, topMargin] = verticalLayout(pageHIn, orientation)
  const previewPaneWidth = dims.previewPaneWidth

  const marginFromTopIn = pageHIn - topMargin
  const contentTopIn = pageHIn - (topMargin - CONTENT_START_OFFSET)
  const letterBandIn = pasteContentHeightIn('letter', orientation)
  const chunkBandIn = Math.min(
    pasteContentHeightIn('letter', orientation),
    pasteContentHeightIn('a4', orientation),
  )
  const packingPadIn = (letterBandIn - chunkBandIn) / 2
  const fontSize = scalePt(HEADER_FONT_PT, pageWidthIn, previewPaneWidth)
  const baselineAdjust = Math.round(fontSize * 0.78)

  return {
    pageWidth: previewPaneWidth,
    pageHeight: scaleIn(pageHIn, pageWidthIn, previewPaneWidth),
    logoTop: scaleIn(marginFromTopIn, pageWidthIn, previewPaneWidth),
    logoLeft: scaleIn(HEADER_LEFT_IN, pageWidthIn, previewPaneWidth),
    logoSize: scalePt(LOGO_PT, pageWidthIn, previewPaneWidth),
    titleTop:
      scaleIn(marginFromTopIn + 12 / PT_PER_IN, pageWidthIn, previewPaneWidth) -
      baselineAdjust,
    composerTop:
      scaleIn(marginFromTopIn + 24 / PT_PER_IN, pageWidthIn, previewPaneWidth) -
      baselineAdjust,
    partNameTop:
      scaleIn(marginFromTopIn + 12 / PT_PER_IN, pageWidthIn, previewPaneWidth) -
      baselineAdjust,
    linkTop:
      scaleIn(marginFromTopIn + 24 / PT_PER_IN, pageWidthIn, previewPaneWidth) -
      baselineAdjust,
    ruleTop: scaleIn(marginFromTopIn + 36 / PT_PER_IN, pageWidthIn, previewPaneWidth),
    contentTop: scaleIn(contentTopIn, pageWidthIn, previewPaneWidth),
    contentHeight: scaleIn(letterBandIn, pageWidthIn, previewPaneWidth),
    contentPaddingTop: scaleIn(packingPadIn, pageWidthIn, previewPaneWidth),
    contentPaddingBottom: scaleIn(packingPadIn, pageWidthIn, previewPaneWidth),
    headerLeft: scaleIn(HEADER_LEFT_IN, pageWidthIn, previewPaneWidth),
    headerRight: scaleIn(HEADER_RIGHT_IN, pageWidthIn, previewPaneWidth),
    textLeft: scaleIn(
      HEADER_LEFT_IN + TEXT_INDENT_PT / PT_PER_IN,
      pageWidthIn,
      previewPaneWidth,
    ),
    fontSize,
    pageNumberBottom: scaleIn(bottomMargin, pageWidthIn, previewPaneWidth),
  }
}

export function previewPageCssVars(layout: PreviewPageLayout): Record<string, string> {
  return {
    '--part-page-width': `${layout.pageWidth}px`,
    '--part-page-height': `${layout.pageHeight}px`,
    '--part-page-logo-top': `${layout.logoTop}px`,
    '--part-page-logo-left': `${layout.logoLeft}px`,
    '--part-page-logo-size': `${layout.logoSize}px`,
    '--part-page-title-top': `${layout.titleTop}px`,
    '--part-page-composer-top': `${layout.composerTop}px`,
    '--part-page-part-name-top': `${layout.partNameTop}px`,
    '--part-page-link-top': `${layout.linkTop}px`,
    '--part-page-rule-top': `${layout.ruleTop}px`,
    '--part-page-content-top': `${layout.contentTop}px`,
    '--part-page-content-height': `${layout.contentHeight}px`,
    '--part-page-content-padding-top': `${layout.contentPaddingTop}px`,
    '--part-page-content-padding-bottom': `${layout.contentPaddingBottom}px`,
    '--part-page-header-left': `${layout.headerLeft}px`,
    '--part-page-header-right': `${layout.headerRight}px`,
    '--part-page-text-left': `${layout.textLeft}px`,
    '--part-page-font-size': `${layout.fontSize}px`,
    '--part-page-number-bottom': `${layout.pageNumberBottom}px`,
  }
}
