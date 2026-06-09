export type PartsetCreateResponse = {
  status: string
  id: string
  action?: string
}

export type ImportProgressResponse = {
  error: string | null
  status: string | null
  progress: number
  total_progress: number
  is_complete: boolean
}

export async function getCsrfToken(): Promise<string> {
  const res = await fetch('/api/v1/csrf-token')
  if (!res.ok) throw new Error('Failed to fetch CSRF token')
  const data = await res.json()
  return data.csrf_token as string
}

export async function createPartsetFromPdf(params: {
  file: File
  title: string
  composer: string
  publisher: string
  copyright: string
  fileHash: string
  csrfToken: string
}): Promise<PartsetCreateResponse> {
  const form = new FormData()
  form.append('score', params.file)
  form.append('title', params.title)
  form.append('composer', params.composer)
  form.append('publisher', params.publisher)
  form.append('copyright', params.copyright)
  form.append('file_hash', params.fileHash)

  const res = await fetch('/api/v1/partsets', {
    method: 'POST',
    headers: { 'X-CSRF-Token': params.csrfToken },
    body: form,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Upload failed')
  }

  return res.json()
}

export async function getImportStatus(privateId: string): Promise<ImportProgressResponse> {
  const res = await fetch(`/api/v1/partsets/${privateId}/import-status`)
  if (!res.ok) throw new Error('Failed to fetch import status')
  return res.json()
}

export async function sha1File(file: File): Promise<string> {
  const buffer = await file.arrayBuffer()
  const hash = await crypto.subtle.digest('SHA-1', buffer)
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}
