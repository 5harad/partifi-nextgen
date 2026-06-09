export const BASE_TAGS = [
  'all',
  'violin',
  'violin I',
  'violin II',
  'viola',
  'cello',
  'guitar',
  'bass',
  'piccolo',
  'flute',
  'oboe',
  'clarinet',
  'bassoon',
  'horn',
  'trumpet',
  'trombones',
  'continuo',
  'piano',
  'organ',
  'harpsichord',
  'soprano',
  'mezzo',
  'alto',
  'contralto',
  'countertenor',
  'tenor',
  'baritone',
]

export function splitTags(value: string): string[] {
  const terms: string[] = []
  for (const part of value.split(/,\s*/)) {
    const term = part.trim().split(/\s+/).join(' ')
    if (term) terms.push(term)
  }
  return terms
}

export function uniqueTags(values: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const value of values) {
    if (!seen.has(value)) {
      seen.add(value)
      out.push(value)
    }
  }
  return out
}

export function lowerFirstLetter(str: string): string {
  return str.charAt(0).toLowerCase() + str.slice(1)
}

export function formatTagsInput(value: string): string {
  const terms = uniqueTags(splitTags(value).map(lowerFirstLetter))
  if (terms.includes('(none)')) return '(none)'
  if (terms.length === 0) return ''
  return terms.join(', ')
}

export function isConfirmedPartTag(tags: string, tagIsSuggestion: boolean): boolean {
  return !tagIsSuggestion && tags !== '' && tags !== '(none)'
}

export function needsPartSuggestion(tags: string, tagIsSuggestion: boolean): boolean {
  return tags === '' || tags === '(none)' || tagIsSuggestion
}

export function isConfirmedLabel(label: string, labelIsSuggestion: boolean): boolean {
  return !labelIsSuggestion && label !== '' && label !== '(none)'
}

export function needsLabelSuggestion(label: string, labelIsSuggestion: boolean): boolean {
  return label === '' || label === '(none)' || labelIsSuggestion
}

export function formatTagsOnFocus(value: string): string {
  const terms = uniqueTags(splitTags(value).map(lowerFirstLetter))
  if (terms.includes('(none)')) return '(none)'
  if (terms.length === 0) return ''
  terms.push('')
  return terms.join(', ')
}
