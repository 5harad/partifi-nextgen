import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { deletePartset, getCsrfToken, updatePartsetMetadata } from '../lib/api'
import { fetchLibrary, updateFavorite } from '../lib/authApi'
import type { LibraryItem } from '../types/library'

function partsetUrl(path: string) {
  return `${window.location.origin}${path}`
}

function LibraryItemPane({
  item,
  onRemove,
  onDelete,
}: {
  item: LibraryItem
  onRemove: () => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(item.title ?? '')
  const [composer, setComposer] = useState(item.composer ?? '')
  const [publisher, setPublisher] = useState(item.publisher ?? '')
  const [error, setError] = useState<string | null>(null)

  const privateId = item.private_id ?? ''
  const editorLink = privateId ? partsetUrl(`/${privateId}`) : ''
  const downloadLink = partsetUrl(`/${item.partset_id}`)

  const saveMetadata = async () => {
    if (!privateId) return
    const nextTitle = title.trim()
    const nextComposer = composer.trim()
    if (!nextTitle || !nextComposer) {
      setError('Please provide a title and composer.')
      return
    }
    try {
      const csrf = await getCsrfToken()
      await updatePartsetMetadata(
        privateId,
        { title: nextTitle, composer: nextComposer, publisher: publisher.trim() },
        csrf,
      )
      setEditing(false)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save metadata')
    }
  }

  const handleDelete = async () => {
    if (!privateId) return
    if (!window.confirm('Are you sure you want to delete these parts?')) return
    try {
      const csrf = await getCsrfToken()
      await deletePartset(privateId, csrf)
      onDelete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete partset')
    }
  }

  const handleRemove = async () => {
    if (!window.confirm('Are you sure you want to remove this score from your library?')) return
    try {
      await updateFavorite(item.partset_id, 'remove')
      onRemove()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove from library')
    }
  }

  const menu = item.admin && privateId ? (
    <div className="download-menu">
      <Link to={`/${privateId}/segment`} className="red">
        edit parts
      </Link>
      {' | '}
      <a href="#" className="red" onClick={(e) => { e.preventDefault(); setEditing(true) }}>
        edit metadata
      </a>
      {' | '}
      <a href="#" className="red" onClick={(e) => { e.preventDefault(); void handleDelete() }}>
        delete parts
      </a>
      {' | '}
      <a href="#" className="red" onClick={(e) => { e.preventDefault(); void handleRemove() }}>
        remove from library
      </a>
    </div>
  ) : !item.admin ? (
    <div className="download-menu">
      <a href="#" className="red" onClick={(e) => { e.preventDefault(); void handleRemove() }}>
        remove from library
      </a>
    </div>
  ) : null

  return (
    <div className="library-item" id={item.partset_id}>
      <div className="box-top" />
      {menu}

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
            <div className="score-composer">
              <input
                type="text"
                className="metadata-edit"
                value={composer}
                onChange={(e) => setComposer(e.target.value)}
              />
            </div>
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
              role="button"
              tabIndex={0}
              onClick={() => void saveMetadata()}
              onKeyDown={() => {}}
            >
              Save
            </div>
            <div
              className="cancel-button"
              style={{ display: 'block' }}
              role="button"
              tabIndex={0}
              onClick={() => setEditing(false)}
              onKeyDown={() => {}}
            >
              Cancel
            </div>
          </>
        ) : (
          <>
            <div className="score-title">{item.title}</div>
            <div style={{ height: 5 }} />
            <div className="score-composer">{item.composer}</div>
            <div style={{ height: 5 }} />
            <div className="score-publisher">{item.publisher}</div>
          </>
        )}
        {error && <p className="red">{error}</p>}
      </div>

      <div className="partset-download">
        <div className="download-title">Download</div>
        {item.score_pdf_url && (
          <>
            <a href={item.score_pdf_url} className="red">
              complete score
            </a>
            <br />
          </>
        )}
        {!item.parts_ready && <span>Parts are not ready for download yet.</span>}
        {item.parts.map((part) => (
          <span key={part.tag}>
            {part.tag}:{' '}
            <a className="red" href={part.letter_url}>
              letter size
            </a>
            {' / '}
            <a className="red" href={part.a4_url}>
              a4
            </a>
            <br />
          </span>
        ))}
      </div>

      <div className="partset-links">
        {item.admin && privateId && (
          <div className="partset-link">
            <div className="partset-link-label">editor link</div>
            <div className="partset-link-link">
              <Link className="red" to={`/${privateId}`}>
                {editorLink}
              </Link>
            </div>
          </div>
        )}
        <div className="partset-link">
          <div className="partset-link-label">download link</div>
          <div className="partset-link-link">
            <Link className="red" to={`/${item.partset_id}`}>
              {downloadLink}
            </Link>
          </div>
        </div>
      </div>

      <div className="box-bottom" />
    </div>
  )
}

function LibraryListItem({
  item,
  selected,
  onSelect,
}: {
  item: LibraryItem
  selected: boolean
  onSelect: () => void
}) {
  return (
    <div
      className={`library-list-item${selected ? ' selected' : ''}`}
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect()
        }
      }}
    >
      <div className="library-list-title">{item.title || 'Untitled'}</div>
      <div className="library-list-composer">{item.composer || 'Unknown composer'}</div>
    </div>
  )
}

export function LibraryPage() {
  const { user, loading: authLoading } = useAuth()
  const [items, setItems] = useState<LibraryItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const removeItem = useCallback((partsetId: string) => {
    setItems((prev) => {
      const next = prev.filter((i) => i.partset_id !== partsetId)
      setSelectedId((current) => {
        if (current !== partsetId) return current
        const removedIndex = prev.findIndex((i) => i.partset_id === partsetId)
        if (next.length === 0) return null
        const nextIndex = Math.min(removedIndex, next.length - 1)
        return next[nextIndex]?.partset_id ?? null
      })
      return next
    })
  }, [])

  const loadLibrary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchLibrary()
      setItems(data.items)
      setSelectedId(data.items[0]?.partset_id ?? null)
    } catch (err) {
      setItems([])
      setSelectedId(null)
      setError(err instanceof Error ? err.message : 'Failed to load library')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (authLoading) return
    if (!user) {
      setLoading(false)
      setError('You must be logged in to view your library.')
      return
    }
    void loadLibrary()
  }, [authLoading, user, loadLibrary])

  const selectedItem = items.find((item) => item.partset_id === selectedId) ?? null

  const emptyMessage =
    error ??
    (loading ? 'Loading…' : 'You do not have any parts saved to your library.')

  return (
    <Layout>
      <div id="main" style={{ height: 750 }}>
        <img
          src="/images/notes_bg.jpg"
          width={1190}
          height={252}
          style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
          alt=""
        />

        <div id="library-layout">
          {items.length === 0 ? (
            <div className="library-item library-empty">
              <div className="box-top" />
              <p id="no-parts">{emptyMessage}</p>
              <div className="box-bottom" />
            </div>
          ) : (
            <>
              <div id="library-list">
                {items.map((item) => (
                  <LibraryListItem
                    key={item.partset_id}
                    item={item}
                    selected={item.partset_id === selectedId}
                    onSelect={() => setSelectedId(item.partset_id)}
                  />
                ))}
              </div>
              <div id="library-detail">
                {selectedItem && (
                  <LibraryItemPane
                    key={selectedItem.partset_id}
                    item={selectedItem}
                    onRemove={() => removeItem(selectedItem.partset_id)}
                    onDelete={() => removeItem(selectedItem.partset_id)}
                  />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </Layout>
  )
}
