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

export function partgenPath(accessId: string, downloadUrl?: string) {
  const base = `/${accessId}/partgen`
  if (!downloadUrl) return base
  return `${base}?download=${encodeURIComponent(downloadUrl)}`
}

export function navigateToPartgen(
  navigate: NavigateFunction,
  accessId: string,
  downloadUrl?: string,
) {
  navigate(partgenPath(accessId, downloadUrl))
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
