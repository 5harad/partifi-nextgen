export const MAX_SCORE_BYTES = 200_000_000
export const MAX_SCORE_MB = 200

export function scoreTooLargeMessage(sizeBytes?: number): string {
  if (sizeBytes !== undefined) {
    const sizeMb = Math.round(sizeBytes / 1_000_000)
    return `This score PDF is too large (${sizeMb} MB). The maximum size is ${MAX_SCORE_MB} MB.`
  }
  return `This score PDF is too large. The maximum size is ${MAX_SCORE_MB} MB.`
}
