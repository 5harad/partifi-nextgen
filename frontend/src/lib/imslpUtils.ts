export type CopyrightValue = 'before 1923' | 'after 1923' | 'unknown'

export function guessCopyrightFromPublisher(publisher: string): CopyrightValue | '' {
  if (!publisher) return ''
  const match = /[^\d]([1-2][0-9]\d\d)([^\d]|$)/.exec(publisher)
  if (!match) return ''
  const year = Number(match[1])
  const currentYear = new Date().getFullYear()
  if (year < 1923) return 'before 1923'
  if (year >= 1923 && year <= currentYear) return 'after 1923'
  return 'unknown'
}

export function normalizeImslpIdInput(raw: string): string {
  const trimmed = raw.trim().replace(/^#/, '')
  if (/^\d+$/.test(trimmed)) return trimmed
  const match = /IMSLP(\d+)/i.exec(raw)
  return match?.[1] ?? trimmed
}

export function imslpReverseLookupUrl(imslpId: string): string {
  return `http://imslp.org/index.php?title=Special:ReverseLookup&action=submit&indexsearch=${encodeURIComponent(imslpId)}`
}
