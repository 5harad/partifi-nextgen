import { imslpReverseLookupUrl } from '../../lib/imslpUtils'

type Props = {
  scorePdfUrl: string | null
  imslpId: string | null
  scoreDownloadName?: string
}

export function ScoreSourceLinks({ scorePdfUrl, imslpId, scoreDownloadName }: Props) {
  const hasScore = Boolean(scorePdfUrl)
  const hasImslp = Boolean(imslpId)
  if (!hasScore && !hasImslp) {
    return null
  }

  return (
    <>
      {hasScore && (
        <a
          href={scorePdfUrl!}
          className="red"
          {...(scoreDownloadName ? { download: scoreDownloadName } : {})}
        >
          complete score
        </a>
      )}
      {hasImslp && (
        <>
          {hasScore && ' | '}
          <a
            className="red"
            href={imslpReverseLookupUrl(imslpId!)}
            target="_blank"
            rel="noreferrer"
          >
            imslp
          </a>
        </>
      )}
      <br />
    </>
  )
}
