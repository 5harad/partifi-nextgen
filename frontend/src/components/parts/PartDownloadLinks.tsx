import { useNavigate } from 'react-router-dom'
import { ensurePartsByAccessId } from '../../lib/api'
import {
  navigateToPartgen,
  partDownloadFilename,
  partgenPath,
  type PartDownloadFormat,
  type PartDownloadItem,
} from '../../lib/partDownloads'

type Props = {
  parts: PartDownloadItem[]
  partsReady: boolean
  /** Public or private id used for partgen routes and ensure-parts API. */
  partgenAccessId: string
  /** When true, enqueue gen_parts on first part click (library). When false, rely on silent regen (download page). */
  ensureOnClick?: boolean
  /** After partgen completes, navigate here instead of the download page. */
  returnTo?: string
}

export function PartDownloadLinks({
  parts,
  partsReady,
  partgenAccessId,
  ensureOnClick = false,
  returnTo,
}: Props) {
  const navigate = useNavigate()

  const handlePartClick = async (
    e: React.MouseEvent<HTMLAnchorElement>,
    tag: string,
    format: PartDownloadFormat,
  ) => {
    e.preventDefault()

    if (ensureOnClick) {
      try {
        await ensurePartsByAccessId(partgenAccessId)
      } catch {
        window.alert('Could not start part generation. Please try again.')
        return
      }
    }

    navigateToPartgen(navigate, partgenAccessId, { tag, format }, returnTo)
  }

  if (parts.length === 0) {
    return null
  }

  return (
    <>
      {parts.map((part) => (
        <span key={part.tag}>
          {part.tag}:{' '}
          <a
            className="red"
            href={
              partsReady
                ? part.letter_url
                : partgenPath(partgenAccessId, { tag: part.tag, format: 'letter' }, returnTo)
            }
            download={partsReady ? partDownloadFilename(part.file_name, 'letter') : undefined}
            onClick={partsReady ? undefined : (e) => void handlePartClick(e, part.tag, 'letter')}
          >
            letter
          </a>
          {' | '}
          <a
            className="red"
            href={
              partsReady
                ? part.a4_url
                : partgenPath(partgenAccessId, { tag: part.tag, format: 'a4' }, returnTo)
            }
            download={partsReady ? partDownloadFilename(part.file_name, 'a4') : undefined}
            onClick={partsReady ? undefined : (e) => void handlePartClick(e, part.tag, 'a4')}
          >
            a4
          </a>
          <br />
        </span>
      ))}
    </>
  )
}
