import { Link } from 'react-router-dom'
import { HelpTip } from '../HelpTip'

type Props = {
  /** Owner/editor view (private download pane). */
  isOwner: boolean
  privateId: string | null
  publicId: string
}

function partsetUrl(path: string) {
  return `${window.location.origin}${path}`
}

async function copyLink(text: string) {
  await navigator.clipboard.writeText(text)
}

function CopyButton({ text }: { text: string }) {
  return (
    <div
      className="copy-button"
      onClick={() => void copyLink(text)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          void copyLink(text)
        }
      }}
      role="button"
      tabIndex={0}
    >
      Copy
    </div>
  )
}

export function PartsetShareLinks({ isOwner, privateId, publicId }: Props) {
  const showEditor = isOwner && Boolean(privateId)
  const editorLink = privateId ? partsetUrl(`/${privateId}`) : ''
  const downloadLink = partsetUrl(`/${publicId}`)

  return (
    <div className="partset-links">
      {showEditor && (
        <div className="partset-link">
          <div className="partset-link-label">editor link</div>
          <div className="partset-link-link">
            <Link className="red" to={`/${privateId}`}>
              {editorLink}
            </Link>
          </div>
          <HelpTip
            className="partset-link-tip editor-tip"
            text="The editor link returns you to this page to edit and download the parts."
          />
          <CopyButton text={editorLink} />
        </div>
      )}
      <div className="partset-link">
        <div className="partset-link-label">download link</div>
        <div className="partset-link-link">
          <Link className="red" to={`/${publicId}`}>
            {downloadLink}
          </Link>
        </div>
        {isOwner && (
          <HelpTip
            className="partset-link-tip download-tip"
            text="Use the download link to share your parts with others. This link lets you download but not edit the parts."
          />
        )}
        <CopyButton text={downloadLink} />
      </div>
    </div>
  )
}
