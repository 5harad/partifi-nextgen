import { useNavigate } from 'react-router-dom'
import { ensurePartsByAccessId } from '../../lib/api'
import {
  navigateToPartgen,
  partDownloadFilename,
  type PartDownloadItem,
} from '../../lib/partDownloads'

type Props = {
  partsetId: string
  parts: PartDownloadItem[]
  partsReady: boolean
  /** Public or private id used for partgen routes and ensure-parts API. */
  partgenAccessId: string
  /** When true, enqueue gen_parts on first part click (library). When false, rely on silent regen (download page). */
  ensureOnClick?: boolean
}

export function PartDownloadLinks({
  partsetId,
  parts,
  partsReady,
  partgenAccessId,
  ensureOnClick = false,
}: Props) {
  const navigate = useNavigate()

  const handlePartClick = async (
    e: React.MouseEvent<HTMLAnchorElement>,
    url: string,
  ) => {
    if (partsReady) return

    e.preventDefault()

    if (ensureOnClick) {
      try {
        await ensurePartsByAccessId(partgenAccessId)
      } catch {
        window.alert('Could not start part generation. Please try again.')
        return
      }
    }

    navigateToPartgen(navigate, partgenAccessId, url)
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
            href={part.letter_url}
            download={partDownloadFilename(partsetId, part.file_name, 'letter')}
            onClick={(e) => void handlePartClick(e, part.letter_url)}
          >
            letter size
          </a>{' '}
          /{' '}
          <a
            className="red"
            href={part.a4_url}
            download={partDownloadFilename(partsetId, part.file_name, 'a4')}
            onClick={(e) => void handlePartClick(e, part.a4_url)}
          >
            a4
          </a>
          <br />
        </span>
      ))}
    </>
  )
}
