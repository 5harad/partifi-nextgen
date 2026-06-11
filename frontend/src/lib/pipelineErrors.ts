import { scoreTooLargeMessage } from './scoreLimits'

const STAGE_MESSAGES: Record<string, string> = {
  import: 'Sorry, there was a problem importing the score.',
  import_size: scoreTooLargeMessage(),
  convert: 'Sorry, there was a problem preparing the score pages.',
  analysis: 'Sorry, there was a problem analyzing the score layout.',
  cut: 'Sorry, there was a problem cutting the parts.',
  paste: 'Sorry, there was a problem assembling the part PDFs.',
}

export function pipelineErrorMessage(stage: string | null | undefined): string {
  if (!stage) {
    return 'Sorry, something went wrong processing this score.'
  }
  return STAGE_MESSAGES[stage] ?? 'Sorry, something went wrong processing this score.'
}

export const POLLING_FAILED_MESSAGE =
  'Could not reach the server. Please refresh the page or try again later.'
