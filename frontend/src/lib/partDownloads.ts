import type { NavigateFunction } from 'react-router-dom'

export type PartDownloadItem = {
  tag: string
  file_name: string
  letter_url: string
  a4_url: string
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

export async function triggerPartFileDownload(url: string): Promise<void> {
  try {
    const res = await fetch(url, { credentials: 'include' })
    if (!res.ok) {
      window.location.assign(url)
      return
    }
    const blob = await res.blob()
    const filename = decodeURIComponent(url.split('/').pop() ?? 'part.pdf')
    const objectUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = objectUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(objectUrl)
  } catch {
    window.location.assign(url)
  }
}
