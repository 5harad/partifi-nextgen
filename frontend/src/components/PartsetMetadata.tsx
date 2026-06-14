import { useCallback, useEffect, useState } from 'react'

export type MetadataFields = {
  title: string
  composer: string
  publisher: string
}

type Source = {
  title?: string | null
  composer?: string | null
  publisher?: string | null
}

function fieldsFromSource(source: Source): MetadataFields {
  return {
    title: source.title ?? '',
    composer: source.composer ?? '',
    publisher: source.publisher ?? '',
  }
}

export function usePartsetMetadata(source: Source) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [title, setTitle] = useState(() => fieldsFromSource(source).title)
  const [composer, setComposer] = useState(() => fieldsFromSource(source).composer)
  const [publisher, setPublisher] = useState(() => fieldsFromSource(source).publisher)

  useEffect(() => {
    if (editing) return
    const next = fieldsFromSource(source)
    setTitle(next.title)
    setComposer(next.composer)
    setPublisher(next.publisher)
  }, [source.title, source.composer, source.publisher, editing])

  const startEdit = useCallback(() => {
    const next = fieldsFromSource(source)
    setTitle(next.title)
    setComposer(next.composer)
    setPublisher(next.publisher)
    setError(null)
    setEditing(true)
  }, [source.title, source.composer, source.publisher])

  const cancelEdit = useCallback(() => {
    setEditing(false)
    setError(null)
  }, [])

  const save = useCallback(
    async (persist: (fields: MetadataFields) => Promise<void>) => {
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
        await persist({
          title: nextTitle,
          composer: nextComposer,
          publisher: nextPublisher,
        })
        setEditing(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to save metadata')
      } finally {
        setSaving(false)
      }
    },
    [title, composer, publisher],
  )

  return {
    editing,
    saving,
    error,
    title,
    composer,
    publisher,
    setTitle,
    setComposer,
    setPublisher,
    startEdit,
    cancelEdit,
    save,
  }
}

type PartsetMetadataProps = {
  display: Source
  editing: boolean
  saving: boolean
  error: string | null
  title: string
  composer: string
  publisher: string
  onTitleChange: (value: string) => void
  onComposerChange: (value: string) => void
  onPublisherChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
  errorClassName?: string
}

export function PartsetMetadata({
  display,
  editing,
  saving,
  error,
  title,
  composer,
  publisher,
  onTitleChange,
  onComposerChange,
  onPublisherChange,
  onSave,
  onCancel,
  errorClassName,
}: PartsetMetadataProps) {
  if (editing) {
    return (
      <>
        <div className="score-title">
          <input
            type="text"
            className="metadata-edit"
            value={title}
            onChange={(e) => onTitleChange(e.target.value)}
          />
        </div>
        <div style={{ height: 5 }} />
        <div className="score-composer">
          <input
            type="text"
            className="metadata-edit"
            value={composer}
            onChange={(e) => onComposerChange(e.target.value)}
          />
        </div>
        <div style={{ height: 5 }} />
        <div className="score-publisher">
          <input
            type="text"
            className="metadata-edit"
            value={publisher}
            onChange={(e) => onPublisherChange(e.target.value)}
          />
        </div>
        <div
          className="save-button"
          style={{ display: 'block' }}
          onClick={onSave}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onSave()
            }
          }}
          role="button"
          tabIndex={0}
        >
          {saving ? 'Saving…' : 'Save'}
        </div>
        <div
          className="cancel-button"
          style={{ display: 'block' }}
          onClick={onCancel}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onCancel()
            }
          }}
          role="button"
          tabIndex={0}
        >
          Cancel
        </div>
        {error && <p className={errorClassName ?? 'red'}>{error}</p>}
      </>
    )
  }

  return (
    <>
      <div className="score-title">{display.title}</div>
      <div style={{ height: 5 }} />
      <div className="score-composer">{display.composer}</div>
      <div style={{ height: 5 }} />
      <div className="score-publisher">{display.publisher}</div>
    </>
  )
}
