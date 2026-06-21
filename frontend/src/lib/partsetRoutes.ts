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

/** Legacy 5-char ids and new xxxxx-xxxxx lowercase ids. */
export const LEGACY_PARTSET_ACCESS_ID_PATTERN = /^[A-Za-z0-9]{5}$/
export const PARTSET_ACCESS_ID_PATTERN = /^[a-z]{5}-[a-z]{5}$/

export function isPartsetAccessId(value: string | undefined): value is string {
  if (!value || STATIC_APP_PATHS.has(value)) {
    return false
  }
  return LEGACY_PARTSET_ACCESS_ID_PATTERN.test(value) || PARTSET_ACCESS_ID_PATTERN.test(value)
}
