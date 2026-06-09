export type SearchResultItem = {
  public_id: string
  score_id: string
  imslp_id: string | null
  title: string | null
  composer: string | null
  publisher: string | null
  score_pdf_url: string
}

export type SearchResponse = {
  results: SearchResultItem[]
}
