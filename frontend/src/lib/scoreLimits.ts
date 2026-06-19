const parsedMb = Number(import.meta.env.VITE_MAX_SCORE_MB)
export const MAX_SCORE_MB = Number.isFinite(parsedMb) && parsedMb > 0 ? parsedMb : 250
export const MAX_SCORE_BYTES = MAX_SCORE_MB * 1_000_000

export function scoreTooLargeMessage(sizeBytes?: number): string {
  if (sizeBytes !== undefined) {
    const sizeMb = Math.round(sizeBytes / 1_000_000)
    return `This score PDF is too large (${sizeMb} MB). The maximum size is ${MAX_SCORE_MB} MB.`
  }
  return `This score PDF is too large. The maximum size is ${MAX_SCORE_MB} MB.`
}
