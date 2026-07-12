/** Mirrors pipeline/pdf_fonts.py — preview header font selection. */

const TIMES_ROMAN_RANGES: [number, number][] = [
  [0x0020, 0x007e],
  [0x00a0, 0x00ff],
  [0x2000, 0x206f],
  [0x2070, 0x209f],
]

const CJK_RANGES: [number, number][] = [
  [0x3040, 0x30ff],
  [0x3400, 0x4dbf],
  [0x4e00, 0x9fff],
  [0xac00, 0xd7af],
  [0xf900, 0xfaff],
  [0xff00, 0xffef],
]

function inRanges(codepoint: number, ranges: [number, number][]): boolean {
  return ranges.some(([start, end]) => codepoint >= start && codepoint <= end)
}

function isLatinChar(ch: string): boolean {
  if (!ch || ch.trim() === '') return true
  return inRanges(ch.codePointAt(0)!, TIMES_ROMAN_RANGES)
}

export function isLatinOnly(text: string): boolean {
  if (!text) return true
  return [...text].every(isLatinChar)
}

export function hasCjk(text: string): boolean {
  return [...text].some((ch) => inRanges(ch.codePointAt(0)!, CJK_RANGES))
}

export function previewHeaderFontFamily(...fields: string[]): string {
  const text = fields.join('')
  if (isLatinOnly(text)) {
    return '"Times New Roman", Times, serif'
  }
  if (hasCjk(text)) {
    return '"Noto Sans SC", "Noto Sans CJK SC", "WenQuanYi Zen Hei", sans-serif'
  }
  return '"Noto Sans", "DejaVu Sans", sans-serif'
}
