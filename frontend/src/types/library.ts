export type LibraryPartItem = {
  tag: string
  file_name: string
  letter_url: string
  a4_url: string
}

export type LibraryItem = {
  partset_id: string
  private_id: string | null
  score_id: string | null
  title: string | null
  composer: string | null
  publisher: string | null
  admin: boolean
  parts_ready: boolean
  parts: LibraryPartItem[]
  score_pdf_url: string | null
}

export type LibraryResponse = {
  items: LibraryItem[]
}
