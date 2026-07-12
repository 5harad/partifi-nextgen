import type { NavigateFunction } from 'react-router-dom'

export type PartDownloadItem = {
  tag: string
  file_name: string
  letter_url: string
  a4_url: string
}

export type PartsPageLocationState = {
  pendingPartDownload?: string
}

export function partDownloadFilename(partsetId: string, fileName: string, format: 'letter' | 'a4') {
  return format === 'letter' ? `${partsetId}_${fileName}` : `${partsetId}_a4_${fileName}`
}

export function partgenPath(accessId: string, downloadUrl?: string, returnTo?: string) {
  const params = new URLSearchParams()
  if (downloadUrl) params.set('download', downloadUrl)
  if (returnTo) params.set('return', returnTo)
  const query = params.toString()
  return query ? `/${accessId}/partgen?${query}` : `/${accessId}/partgen`
}

export function navigateToPartgen(
  navigate: NavigateFunction,
  accessId: string,
  downloadUrl?: string,
  returnTo?: string,
) {
  navigate(partgenPath(accessId, downloadUrl, returnTo))
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
