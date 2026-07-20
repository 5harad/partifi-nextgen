import type { OrientationDataResponse } from '../types/orientation'
import type { PageSegmentData, SegmentDataResponse } from '../types/segment'
import type {
  PartgenProgressResponse,
  PartsDataResponse,
  PreviewDataResponse,
} from '../types/preview'
import type { SearchResponse } from '../types/search'
import type { ImslpInfoResponse } from '../types/imslp'
import { apiErrorDetail } from './apiErrors'

async function apiFetch(input: RequestInfo, init?: RequestInit): Promise<Response> {
  return fetch(input, { ...init, credentials: 'include' })
}

export type PartsetCreateResponse = {
  status: string
  id: string
  action?: string
}

export type ImportProgressResponse = {
  error: string | null
  error_message: string | null
  status: string | null
  progress: number
  total_progress: number
  is_complete: boolean
}

export async function getCsrfToken(): Promise<string> {
  const res = await apiFetch('/api/v1/csrf-token')
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

  const res = await apiFetch('/api/v1/partsets', {
    method: 'POST',
    headers: { 'X-CSRF-Token': params.csrfToken },
    body: form,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorDetail(err, 'Upload failed'))
  }

  return res.json()
}

export async function getImportStatus(privateId: string): Promise<ImportProgressResponse> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/import-status`)
  if (!res.ok) throw new Error('Failed to fetch import status')
  return res.json()
}

export async function ensureImportByPrivateId(privateId: string): Promise<void> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/ensure-import`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorDetail(err, 'Failed to start import'))
  }
}

export async function retryPartsetPageCache(
  privateId: string,
  csrfToken: string,
): Promise<{ status: string }> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/retry-page-cache`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorDetail(err, 'Failed to retry page images'))
  }
  return res.json()
}

export async function retryPartsetPipeline(
  privateId: string,
  csrfToken: string,
): Promise<{ status: string; stage: string; job_id: string | null }> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/retry-pipeline`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorDetail(err, 'Failed to retry'))
  }
  return res.json()
}

export async function retryPartsetPipelineByAccessId(
  accessId: string,
  csrfToken: string,
): Promise<{ status: string; stage: string; job_id: string | null }> {
  const res = await apiFetch(`/api/v1/access/${accessId}/retry-pipeline`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorDetail(err, 'Failed to retry'))
  }
  return res.json()
}

export async function getSegmentData(privateId: string): Promise<SegmentDataResponse> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/segment-data`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load segment data')
  }
  return res.json()
}

export async function getOrientationData(privateId: string): Promise<OrientationDataResponse> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/orientation-data`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load orientation data')
  }
  return res.json()
}

export async function reorientPartset(
  privateId: string,
  rotationDegrees: number,
  csrfToken: string,
): Promise<{ status: string; job_id: string }> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/reorient`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify({ rotation_degrees: rotationDegrees }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorDetail(err, 'Reorient failed'))
  }
  return res.json()
}

export async function savePageSegments(
  privateId: string,
  page: number,
  data: PageSegmentData,
  csrfToken: string,
): Promise<void> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/pages/${page}/segments`, {
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

export async function saveAllPageSegments(
  privateId: string,
  pages: Record<string, PageSegmentData>,
  csrfToken: string,
): Promise<void> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/segments`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify({ pages }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to save segments')
  }
}

export async function getPreviewData(privateId: string): Promise<PreviewDataResponse> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/preview-data`)
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
  const res = await apiFetch(`/api/v1/partsets/${privateId}/layout`, {
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
  const res = await apiFetch(`/api/v1/partsets/${privateId}/parts/combine`, {
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
): Promise<{ job_id: string | null; parts_ready: boolean }> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/generate`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to start part generation')
  }
  return res.json()
}

export async function getPartgenStatus(privateId: string): Promise<PartgenProgressResponse> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/partgen-status`)
  if (!res.ok) throw new Error('Failed to fetch part generation status')
  return res.json()
}

export async function getPartgenStatusByAccessId(
  accessId: string,
): Promise<PartgenProgressResponse> {
  const res = await apiFetch(`/api/v1/access/${accessId}/partgen-status`)
  if (!res.ok) throw new Error('Failed to fetch part generation status')
  return res.json()
}

export async function ensurePartsByAccessId(accessId: string): Promise<void> {
  const res = await apiFetch(`/api/v1/access/${accessId}/ensure-parts`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to start part generation')
  }
}

export async function getPartsByAccessId(accessId: string): Promise<PartsDataResponse> {
  const res = await apiFetch(`/api/v1/access/${accessId}/parts`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load parts')
  }
  return res.json()
}

export async function updatePartsetMetadata(
  privateId: string,
  body: { title: string; composer: string; publisher: string },
  csrfToken: string,
): Promise<void> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}/metadata`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update metadata')
  }
}

export async function deletePartset(privateId: string, csrfToken: string): Promise<void> {
  const res = await apiFetch(`/api/v1/partsets/${privateId}`, {
    method: 'DELETE',
    headers: { 'X-CSRF-Token': csrfToken },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to delete partset')
  }
}

export async function searchPartsets(query: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query })
  const res = await apiFetch(`/api/v1/search?${params}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Search failed')
  }
  return res.json()
}

export async function getImslpInfo(
  imslpId: string,
  signal?: AbortSignal,
): Promise<ImslpInfoResponse> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 20000)

  const abortFromParent = () => controller.abort()
  signal?.addEventListener('abort', abortFromParent)

  try {
    const res = await apiFetch(`/api/v1/imslp/${encodeURIComponent(imslpId)}/info`, {
      signal: controller.signal,
    })
    if (res.status === 404 || res.status === 400) {
      const err = await res.json().catch(() => ({}))
      throw new Error(apiErrorDetail(err, 'Edition not found.'))
    }
    if (res.status === 504) {
      throw new Error('IMSLP lookup timed out. Try again in a moment.')
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(apiErrorDetail(err, 'IMSLP lookup failed'))
    }
    return res.json()
  } catch (err) {
    if (controller.signal.aborted && !signal?.aborted) {
      throw new Error('IMSLP lookup timed out. Try again in a moment.')
    }
    throw err
  } finally {
    window.clearTimeout(timeout)
    signal?.removeEventListener('abort', abortFromParent)
  }
}

export async function createPartsetFromImslp(
  body: {
    imslp_id: string
    title: string
    composer: string
    publisher: string
    copyright: string
  },
  csrfToken: string,
): Promise<PartsetCreateResponse> {
  const res = await apiFetch('/api/v1/partsets/imslp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorDetail(err, 'Failed to import from IMSLP'))
  }
  return res.json()
}

export async function createPartsetFromScore(
  body: {
    score_id: string
    title: string
    composer: string
    publisher: string
    copyright: string
  },
  csrfToken: string,
): Promise<PartsetCreateResponse> {
  const res = await apiFetch('/api/v1/partsets/from-score', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create partset')
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
