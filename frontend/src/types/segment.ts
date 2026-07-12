export type SegmentItem = {
  pos: [number, number]
  tags: string
  tag_is_suggestion: boolean
  label: string
  label_is_suggestion: boolean
}

export type PageSegmentData = {
  left_margin: number
  right_margin: number
  rotation: number
  segments: SegmentItem[]
}

import type { Orientation } from '../lib/pageDimensions'

export type { Orientation }

export type SegmentDataResponse = {
  score_id: string
  partset_id: string
  private_id: string
  orientation: Orientation
  num_pages: number
  pages: Record<string, PageSegmentData>
  image_urls: {
    lowres: Record<string, string>
    thumbs: Record<string, string>
  }
  images_ready: boolean
  images_warming: boolean
  image_progress: number
  image_cache_error_message?: string | null
}

export type RegionState = {
  id: string
  topPx: number
  tags: string
  tagIsSuggestion: boolean
  label: string
  labelIsSuggestion: boolean
}
