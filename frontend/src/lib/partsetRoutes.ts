/** Reserved first path segments (static pages). Listed before /:accessId in the router. */
export const STATIC_APP_PATHS = new Set([
  'about',
  'terms',
  'privacy',
  'howto',
  'faq',
  'search',
  'library',
])

/** Public/private partset ids (legacy + new). */
export const PARTSET_ACCESS_ID_PATTERN = /^[A-Za-z0-9]{5}$/

export function isPartsetAccessId(value: string | undefined): value is string {
  return Boolean(value && PARTSET_ACCESS_ID_PATTERN.test(value) && !STATIC_APP_PATHS.has(value))
}
