import type { PageSegmentData, SegmentDataResponse } from '../types/segment'
import type {
  PartgenProgressResponse,
  PartsDataResponse,
  PreviewDataResponse,
} from '../types/preview'

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

export async function getSegmentData(privateId: string): Promise<SegmentDataResponse> {
  const res = await fetch(`/api/v1/partsets/${privateId}/segment-data`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load segment data')
  }
  return res.json()
}

export async function savePageSegments(
  privateId: string,
  page: number,
  data: PageSegmentData,
  csrfToken: string,
): Promise<void> {
  const res = await fetch(`/api/v1/partsets/${privateId}/pages/${page}/segments`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to save segments')
  }
}

export async function getPreviewData(privateId: string): Promise<PreviewDataResponse> {
  const res = await fetch(`/api/v1/partsets/${privateId}/preview-data`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load preview data')
  }
  return res.json()
}

export async function saveLayout(
  privateId: string,
  body: { breaks: Record<string, number[]>; spacings: Record<string, number> },
  csrfToken: string,
): Promise<void> {
  const res = await fetch(`/api/v1/partsets/${privateId}/layout`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to save layout')
  }
}

export async function combineParts(
  privateId: string,
  action: 'add' | 'remove',
  tag: string,
  csrfToken: string,
): Promise<void> {
  const res = await fetch(`/api/v1/partsets/${privateId}/parts/combine`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify({ action, tag }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update combined parts')
  }
}

export async function startPartGeneration(
  privateId: string,
  csrfToken: string,
): Promise<void> {
  const res = await fetch(`/api/v1/partsets/${privateId}/generate`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to start part generation')
  }
}

export async function getPartgenStatus(privateId: string): Promise<PartgenProgressResponse> {
  const res = await fetch(`/api/v1/partsets/${privateId}/partgen-status`)
  if (!res.ok) throw new Error('Failed to fetch part generation status')
  return res.json()
}

export async function getPartsData(privateId: string): Promise<PartsDataResponse> {
  const res = await fetch(`/api/v1/partsets/${privateId}/parts`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load parts')
  }
  return res.json()
}

export async function sha1File(file: File): Promise<string> {
  const buffer = await file.arrayBuffer()
  const hash = await crypto.subtle.digest('SHA-1', buffer)
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}
