import type { Orientation } from '../lib/pageDimensions'

export type PreviewDataResponse = {
  partset_id: string
  private_id: string
  title: string | null
  composer: string | null
  orientation: Orientation
  part_names: string[]
  combined_part_names: string[]
  part_segments: Record<string, number[]>
  segment_heights: number[]
  segment_widths: number[]
  segment_labels: string[]
  breaks: Record<string, number[]>
  spacings: Record<string, number>
  left_margin: number
  segment_urls: Record<string, string>
  images_ready: boolean
  images_warming: boolean
  image_progress: number
}

export type PartgenProgressResponse = {
  error: string | null
  status: string | null
  progress: number
  total_progress: number
  is_complete: boolean
  in_progress: boolean
}

export type PartsDataResponse = {
  partset_id: string
  private_id: string | null
  public_id: string
  mode: 'owner' | 'public'
  title: string | null
  composer: string | null
  publisher: string | null
  score_pdf_url: string | null
  parts: Array<{
    tag: string
    file_name: string
    letter_url: string
    a4_url: string
  }>
  parts_ready: boolean
  imslp_id: string | null
}
