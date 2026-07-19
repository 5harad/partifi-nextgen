import type { NavigateFunction } from 'react-router-dom'

export type PartDownloadItem = {
  tag: string
  file_name: string
  letter_url: string
  a4_url: string
}

export type PartDownloadFormat = 'letter' | 'a4'

export type PartgenDownloadTarget = {
  tag: string
  format: PartDownloadFormat
}

export type PartsPageLocationState = {
  pendingPartDownload?: string
}

export function partDownloadFilename(fileName: string, format: PartDownloadFormat) {
  if (format === 'letter') return fileName
  const stem = fileName.endsWith('.pdf') ? fileName.slice(0, -4) : fileName
  return `${stem}-a4.pdf`
}

export function partDownloadUrl(
  parts: PartDownloadItem[],
  target: PartgenDownloadTarget,
): string | null {
  const part = parts.find((candidate) => candidate.tag === target.tag)
  if (!part) return null
  return target.format === 'a4' ? part.a4_url : part.letter_url
}

export function parsePartDownloadFormat(value: string | null): PartDownloadFormat | null {
  return value === 'letter' || value === 'a4' ? value : null
}

export function partgenPath(
  accessId: string,
  target?: PartgenDownloadTarget,
  returnTo?: string,
) {
  const params = new URLSearchParams()
  if (target) {
    params.set('part', target.tag)
    params.set('format', target.format)
  }
  if (returnTo) params.set('return', returnTo)
  const query = params.toString()
  return query ? `/${accessId}/partgen?${query}` : `/${accessId}/partgen`
}

export function navigateToPartgen(
  navigate: NavigateFunction,
  accessId: string,
  target?: PartgenDownloadTarget,
  returnTo?: string,
) {
  navigate(partgenPath(accessId, target, returnTo))
}

export function partgenReturnPath(searchParams: URLSearchParams, accessId: string): string {
  const returnTo = searchParams.get('return')
  if (returnTo?.startsWith('/') && !returnTo.startsWith('//')) {
    return returnTo
  }
  return `/${accessId}`
}

/** Start a file download from a stable page (after partgen navigation). */
export function startPartFileDownload(url: string): void {
  const iframe = document.createElement('iframe')
  iframe.style.display = 'none'
  iframe.src = url
  document.body.appendChild(iframe)
  window.setTimeout(() => iframe.remove(), 120_000)
}
