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

export type SegmentDataResponse = {
  score_id: string
  partset_id: string
  private_id: string
  num_pages: number
  pages: Record<string, PageSegmentData>
  image_urls: {
    lowres: Record<string, string>
    thumbs: Record<string, string>
  }
}

export type RegionState = {
  id: string
  topPx: number
  tags: string
  tagIsSuggestion: boolean
  label: string
  labelIsSuggestion: boolean
}
