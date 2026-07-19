import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { PartsetMetadata, usePartsetMetadata } from '../components/PartsetMetadata'
import { PartDownloadLinks } from '../components/parts/PartDownloadLinks'
import { PartsetShareLinks } from '../components/parts/PartsetShareLinks'
import { ScoreSourceLinks } from '../components/parts/ScoreSourceLinks'
import { useAuth } from '../context/AuthContext'
import {
  deletePartset,
  getCsrfToken,
  getPartgenStatusByAccessId,
  getPartsByAccessId,
  updatePartsetMetadata,
} from '../lib/api'
import { fetchLibrary, updateFavorite } from '../lib/authApi'
import { startPartFileDownload, type PartsPageLocationState } from '../lib/partDownloads'
import { useNoIndex } from '../lib/useNoIndex'
import type { LibraryItem } from '../types/library'

function LibraryItemPane({
  item,
  onRemove,
  onDelete,
  onMetadataSaved,
}: {
  item: LibraryItem
  onRemove: () => void
  onDelete: () => void
  onMetadataSaved: (partsetId: string, fields: { title: string; composer: string; publisher: string }) => void
}) {
  const privateId = item.private_id ?? ''
  const partgenAccessId = privateId || item.partset_id

  const metadata = usePartsetMetadata(item)
  const [display, setDisplay] = useState({
    title: item.title,
    composer: item.composer,
    publisher: item.publisher,
  })

  useEffect(() => {
    setDisplay({
      title: item.title,
      composer: item.composer,
      publisher: item.publisher,
    })
  }, [item.title, item.composer, item.publisher, item.partset_id])

  const saveMetadata = useCallback(async () => {
    if (!privateId) return
    await metadata.save(async (fields) => {
      const csrf = await getCsrfToken()
      await updatePartsetMetadata(privateId, fields, csrf)
      setDisplay({
        title: fields.title,
        composer: fields.composer,
        publisher: fields.publisher || null,
      })
      onMetadataSaved(item.partset_id, fields)
    })
  }, [privateId, metadata, item.partset_id, onMetadataSaved])

  const handleDelete = async () => {
    if (!privateId) return
    if (!window.confirm('Are you sure you want to delete these parts?')) return
    try {
      const csrf = await getCsrfToken()
      await deletePartset(privateId, csrf)
      onDelete()
    } catch (err) {
      metadata.cancelEdit()
      // Surface via metadata error by reusing save error path — use alert for delete-only errors
      window.alert(err instanceof Error ? err.message : 'Failed to delete partset')
    }
  }

  const handleRemove = async () => {
    if (!window.confirm('Are you sure you want to remove this score from your library?')) return
    try {
      await updateFavorite(item.partset_id, 'remove')
      onRemove()
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to remove from library')
    }
  }

  const menu = item.admin && privateId ? (
    <div className="download-menu">
      <Link to={`/${privateId}/segment`} className="red">
        edit parts
      </Link>
      {' | '}
      <a href="#" className="red" onClick={(e) => { e.preventDefault(); metadata.startEdit() }}>
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
        <PartsetMetadata
          display={display}
          editing={metadata.editing}
          saving={metadata.saving}
          error={metadata.error}
          title={metadata.title}
          composer={metadata.composer}
          publisher={metadata.publisher}
          onTitleChange={metadata.setTitle}
          onComposerChange={metadata.setComposer}
          onPublisherChange={metadata.setPublisher}
          onSave={() => void saveMetadata()}
          onCancel={metadata.cancelEdit}
        />
      </div>

      <div className="partset-download">
        <div className="download-title">Download</div>
        <ScoreSourceLinks scorePdfUrl={item.score_pdf_url} imslpId={item.imslp_id} />
        <PartDownloadLinks
          parts={item.parts}
          partsReady={item.parts_ready}
          partgenAccessId={partgenAccessId}
          ensureOnClick
          returnTo={`/library?partset=${encodeURIComponent(item.partset_id)}`}
        />
      </div>

      <PartsetShareLinks
        isOwner={item.admin}
        privateId={privateId || null}
        publicId={item.partset_id}
      />

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
  useNoIndex()
  const { user, loading: authLoading } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [items, setItems] = useState<LibraryItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const handledPendingDownloadRef = useRef<string | null>(null)

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

  const handleMetadataSaved = useCallback(
    (partsetId: string, fields: { title: string; composer: string; publisher: string }) => {
      setItems((prev) =>
        prev.map((item) =>
          item.partset_id === partsetId
            ? {
                ...item,
                title: fields.title,
                composer: fields.composer,
                publisher: fields.publisher || null,
                parts_ready: false,
              }
            : item,
        ),
      )
    },
    [],
  )

  const loadLibrary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchLibrary()
      setItems(data.items)
      const fromQuery = searchParams.get('partset')
      const selected =
        fromQuery && data.items.some((item) => item.partset_id === fromQuery)
          ? fromQuery
          : data.items[0]?.partset_id ?? null
      setSelectedId(selected)
    } catch (err) {
      setItems([])
      setSelectedId(null)
      setError(err instanceof Error ? err.message : 'Failed to load library')
    } finally {
      setLoading(false)
    }
  }, [searchParams])

  useEffect(() => {
    const fromQuery = searchParams.get('partset')
    if (fromQuery && items.some((item) => item.partset_id === fromQuery)) {
      setSelectedId(fromQuery)
    }
  }, [searchParams, items])

  useEffect(() => {
    if (authLoading) return
    if (!user) {
      setLoading(false)
      setError('You must be logged in to view your library.')
      return
    }
    void loadLibrary()
  }, [authLoading, user, loadLibrary])

  useEffect(() => {
    const state = location.state as PartsPageLocationState | null
    const pendingUrl = state?.pendingPartDownload
    if (!pendingUrl || handledPendingDownloadRef.current === pendingUrl) return

    const partsetId = searchParams.get('partset')
    const item = partsetId
      ? items.find((entry) => entry.partset_id === partsetId)
      : items.find((entry) => entry.partset_id === selectedId)
    if (!item) return

    const accessId = item.private_id || item.partset_id
    let cancelled = false
    let timeoutId = 0

    const finish = () => {
      if (cancelled || handledPendingDownloadRef.current === pendingUrl) return
      handledPendingDownloadRef.current = pendingUrl
      startPartFileDownload(pendingUrl)
      navigate({ pathname: '/library', search: location.search }, { replace: true, state: {} })
    }

    if (item.parts_ready) {
      finish()
      return
    }

    const poll = async () => {
      try {
        const status = await getPartgenStatusByAccessId(accessId)
        if (cancelled) return
        if (status.is_complete) {
          const fresh = await getPartsByAccessId(accessId)
          if (cancelled) return
          setItems((prev) =>
            prev.map((entry) =>
              entry.partset_id === item.partset_id
                ? { ...entry, parts_ready: fresh.parts_ready, parts: fresh.parts }
                : entry,
            ),
          )
          finish()
          return
        }
      } catch {
        // Transient errors — keep polling until partgen reports complete.
      }
      if (!cancelled) {
        timeoutId = window.setTimeout(poll, 500)
      }
    }

    void poll()

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [items, selectedId, location.search, location.state, navigate, searchParams])

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
                    onMetadataSaved={handleMetadataSaved}
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
