import { useEffect, useState } from 'react'

export type SessionImageRequest = {
  key: string
  url: string
  priority: 'high' | 'low'
}

type PriorityRequestInit = RequestInit & {
  priority?: 'high' | 'low'
}

const MAX_CONCURRENT_IMAGE_REQUESTS = 16

/**
 * Keeps dynamic images in memory for the lifetime of a mounted editor.
 * Requests always bypass the browser's persistent HTTP cache. A bounded queue
 * leaves browser capacity for the editor's static chrome while consumers render
 * the returned Blob URLs, so changing views never initiates a second request.
 */
export function useSessionImageCache(
  requests: readonly SessionImageRequest[],
  sessionKey: unknown,
): Record<string, string> {
  const [cache, setCache] = useState<{ sessionKey: unknown; imageUrls: Record<string, string> }>({
    sessionKey: null,
    imageUrls: {},
  })
  const imageUrls = cache.sessionKey === sessionKey ? cache.imageUrls : {}

  useEffect(() => {
    const controller = new AbortController()
    const objectUrls: string[] = []
    let pending: Record<string, string> = {}
    let frame = 0
    let active = true
    let nextRequest = 0

    const publish = () => {
      frame = 0
      if (!active) return
      if (!Object.keys(pending).length) return
      const next = pending
      pending = {}
      setCache((current) => ({
        sessionKey,
        imageUrls: current.sessionKey === sessionKey ? { ...current.imageUrls, ...next } : next,
      }))
    }

    const load = async ({ key, url, priority }: SessionImageRequest) => {
      try {
        const response = await fetch(url, {
          cache: 'no-store',
          credentials: 'include',
          priority,
          signal: controller.signal,
        } as PriorityRequestInit)
        if (!response.ok) throw new Error(`Image request failed: ${response.status}`)
        const blob = await response.blob()
        if (!active) return
        const objectUrl = URL.createObjectURL(blob)
        objectUrls.push(objectUrl)
        pending[key] = objectUrl
        if (!frame) frame = requestAnimationFrame(publish)
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error(`Failed to preload image ${url}`, error)
        }
      }
    }

    const loadNext = () => {
      if (!active) return
      const request = requests[nextRequest]
      nextRequest += 1
      if (!request) return
      void load(request).finally(loadNext)
    }
    for (let ndx = 0; ndx < Math.min(MAX_CONCURRENT_IMAGE_REQUESTS, requests.length); ndx++) {
      loadNext()
    }

    return () => {
      active = false
      controller.abort()
      if (frame) cancelAnimationFrame(frame)
      for (const objectUrl of objectUrls) URL.revokeObjectURL(objectUrl)
    }
  }, [requests, sessionKey])

  return imageUrls
}
