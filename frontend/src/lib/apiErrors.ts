/** Extract a user-facing message from a FastAPI error JSON body. */
export function apiErrorDetail(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') {
    return fallback
  }
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    if (typeof first === 'object' && first !== null && 'msg' in first) {
      return String((first as { msg: unknown }).msg)
    }
  }
  return fallback
}
