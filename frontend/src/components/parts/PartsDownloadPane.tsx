import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  deletePartset,
  getCsrfToken,
  updatePartsetMetadata,
} from '../../lib/api'
import type { PartsDataResponse } from '../../types/preview'

type Props = {
  data: PartsDataResponse
  onDataChange: (data: PartsDataResponse) => void
}

function partsetUrl(path: string) {
  return `${window.location.origin}${path}`
}

async function copyLink(text: string) {
  await navigator.clipboard.writeText(text)
}

export function PartsDownloadPane({ data, onDataChange }: Props) {
  const isOwner = data.mode === 'owner'
  const privateId = data.private_id ?? ''
  const publicId = data.public_id

  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(data.title ?? '')
  const [composer, setComposer] = useState(data.composer ?? '')
  const [publisher, setPublisher] = useState(data.publisher ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const editorLink = partsetUrl(`/${privateId}/parts`)
  const downloadLink = partsetUrl(`/${publicId}`)

  const startEdit = useCallback(() => {
    setTitle(data.title ?? '')
    setComposer(data.composer ?? '')
    setPublisher(data.publisher ?? '')
    setEditing(true)
    setError(null)
  }, [data.title, data.composer, data.publisher])

  const cancelEdit = useCallback(() => {
    setEditing(false)
    setError(null)
  }, [])

  const saveMetadata = useCallback(async () => {
    const nextTitle = title.trim()
    const nextComposer = composer.trim()
    const nextPublisher = publisher.trim()
    if (!nextTitle || !nextComposer) {
      setError('Please provide a title and composer.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const csrf = await getCsrfToken()
      await updatePartsetMetadata(
        privateId,
        { title: nextTitle, composer: nextComposer, publisher: nextPublisher },
        csrf,
      )
      onDataChange({
        ...data,
        title: nextTitle,
        composer: nextComposer,
        publisher: nextPublisher || null,
      })
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save metadata')
    } finally {
      setSaving(false)
    }
  }, [title, composer, publisher, privateId, data, onDataChange])

  const handleDelete = useCallback(async () => {
    if (!window.confirm('Are you sure you want to delete these parts?')) return
    try {
      const csrf = await getCsrfToken()
      await deletePartset(privateId, csrf)
      window.location.href = '/'
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete partset')
    }
  }, [privateId])

  return (
    <div className="download-pane">
      <div className="box-top" />
      {isOwner && (
        <div className="download-menu">
          <Link to={`/${privateId}/segment`} className="red">
            edit parts
          </Link>
          {' | '}
          <a href="#" className="red" onClick={(e) => { e.preventDefault(); startEdit() }}>
            edit metadata
          </a>
          {' | '}
          <a href="#" className="red" onClick={(e) => { e.preventDefault(); void handleDelete() }}>
            delete parts
          </a>
        </div>
      )}
      <div className="partset-info">
        {editing ? (
          <>
            <div className="score-title">
              <input
                type="text"
                className="metadata-edit"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div style={{ height: 5 }} />
            <div className="score-composer">
              <input
                type="text"
                className="metadata-edit"
                value={composer}
                onChange={(e) => setComposer(e.target.value)}
              />
            </div>
            <div style={{ height: 5 }} />
            <div className="score-publisher">
              <input
                type="text"
                className="metadata-edit"
                value={publisher}
                onChange={(e) => setPublisher(e.target.value)}
              />
            </div>
            <div
              className="save-button"
              style={{ display: 'block' }}
              onClick={() => void saveMetadata()}
              onKeyDown={() => {}}
              role="button"
              tabIndex={0}
            >
              {saving ? 'Saving…' : 'Save'}
            </div>
            <div
              className="cancel-button"
              style={{ display: 'block' }}
              onClick={cancelEdit}
              onKeyDown={() => {}}
              role="button"
              tabIndex={0}
            >
              Cancel
            </div>
          </>
        ) : (
          <>
            <div className="score-title">{data.title}</div>
            <div style={{ height: 5 }} />
            <div className="score-composer">{data.composer}</div>
            <div style={{ height: 5 }} />
            <div className="score-publisher">{data.publisher}</div>
          </>
        )}
      </div>
      {error && <p className="red" style={{ padding: '0 20px' }}>{error}</p>}
      <div className="partset-download">
        <div className="download-title">Download</div>
        {data.score_pdf_url && (
          <>
            <a
              href={data.score_pdf_url}
              className="red"
              download={`${data.partset_id}_score.pdf`}
            >
              complete score
            </a>
            <br />
          </>
        )}
        {data.parts.map((part) => (
          <span key={part.tag}>
            {part.tag}:{' '}
            <a
              className="red"
              href={part.letter_url}
              download={`${data.partset_id}_${part.file_name}`}
            >
              letter size
            </a>{' '}
            /{' '}
            <a
              className="red"
              href={part.a4_url}
              download={`${data.partset_id}_a4_${part.file_name}`}
            >
              a4
            </a>
            <br />
          </span>
        ))}
      </div>
      <div className="partset-links">
        {isOwner && (
          <div className="partset-link">
            <div className="partset-link-label">editor link</div>
            <div className="partset-link-link">
              <Link className="red" to={`/${privateId}/parts`}>
                {editorLink}
              </Link>
            </div>
            <div
              className="partset-link-tip editor-tip"
              title="The editor link returns you to this page to edit and download the parts."
            />
            <div
              className="copy-button"
              onClick={() => void copyLink(editorLink)}
              onKeyDown={() => {}}
              role="button"
              tabIndex={0}
            >
              Copy
            </div>
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
            <div
              className="partset-link-tip download-tip"
              title="Use the download link to share your parts with others. This link lets you download but not edit the parts."
            />
          )}
          <div
            className="copy-button"
            onClick={() => void copyLink(downloadLink)}
            onKeyDown={() => {}}
            role="button"
            tabIndex={0}
          >
            Copy
          </div>
        </div>
      </div>
      <div className="box-bottom" />
    </div>
  )
}
