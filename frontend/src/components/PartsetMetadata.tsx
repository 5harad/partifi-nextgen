import { useCallback, useEffect, useState } from 'react'
import { CopyrightTip } from './CopyrightTip'
import type { CopyrightValue } from '../lib/imslpUtils'

export type MetadataFields = {
  title: string
  composer: string
  publisher: string
  copyright: CopyrightValue
}

type Source = {
  title?: string | null
  composer?: string | null
  publisher?: string | null
  copyright?: string | null
}

const COPYRIGHT_LABELS: Record<CopyrightValue, string> = {
  'before 1923': 'Published before 1923',
  'after 1923': 'Published in or after 1923',
  unknown: 'Unknown copyright',
}

function normalizeCopyright(value: string | null | undefined): CopyrightValue {
  if (value === 'before 1923' || value === 'after 1923' || value === 'unknown') {
    return value
  }
  return 'unknown'
}

function fieldsFromSource(source: Source): MetadataFields {
  return {
    title: source.title ?? '',
    composer: source.composer ?? '',
    publisher: source.publisher ?? '',
    copyright: normalizeCopyright(source.copyright),
  }
}

export function usePartsetMetadata(source: Source) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const initial = fieldsFromSource(source)
  const [title, setTitle] = useState(initial.title)
  const [composer, setComposer] = useState(initial.composer)
  const [publisher, setPublisher] = useState(initial.publisher)
  const [copyright, setCopyright] = useState<CopyrightValue>(initial.copyright)

  useEffect(() => {
    if (editing) return
    const next = fieldsFromSource(source)
    setTitle(next.title)
    setComposer(next.composer)
    setPublisher(next.publisher)
    setCopyright(next.copyright)
  }, [source.title, source.composer, source.publisher, source.copyright, editing])

  const startEdit = useCallback(() => {
    const next = fieldsFromSource(source)
    setTitle(next.title)
    setComposer(next.composer)
    setPublisher(next.publisher)
    setCopyright(next.copyright)
    setError(null)
    setEditing(true)
  }, [source.title, source.composer, source.publisher, source.copyright])

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
      if (!copyright) {
        setError('Please select a copyright option.')
        return
      }
      setSaving(true)
      setError(null)
      try {
        await persist({
          title: nextTitle,
          composer: nextComposer,
          publisher: nextPublisher,
          copyright,
        })
        setEditing(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to save metadata')
      } finally {
        setSaving(false)
      }
    },
    [title, composer, publisher, copyright],
  )

  return {
    editing,
    saving,
    error,
    title,
    composer,
    publisher,
    copyright,
    setTitle,
    setComposer,
    setPublisher,
    setCopyright,
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
  copyright: CopyrightValue
  showCopyright?: boolean
  onTitleChange: (value: string) => void
  onComposerChange: (value: string) => void
  onPublisherChange: (value: string) => void
  onCopyrightChange: (value: CopyrightValue) => void
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
  copyright,
  showCopyright = false,
  onTitleChange,
  onComposerChange,
  onPublisherChange,
  onCopyrightChange,
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
            placeholder="Edition"
            onChange={(e) => onPublisherChange(e.target.value)}
          />
        </div>
        {showCopyright ? (
          <>
            <div style={{ height: 5 }} />
            <div className="metadata-copyright-row">
              <span className="metadata-copyright-label">
                copyright
                <CopyrightTip className="metadata-copyright-tip" />
              </span>
              <select
                className="metadata-edit metadata-copyright-select"
                value={copyright}
                onChange={(e) => onCopyrightChange(e.target.value as CopyrightValue)}
              >
                <option value="before 1923">Published before 1923</option>
                <option value="after 1923">Published in or after 1923</option>
                <option value="unknown">Unknown copyright</option>
              </select>
            </div>
          </>
        ) : null}
        <div
          className={`save-button${showCopyright ? ' save-button-with-copyright' : ''}`}
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
          className={`cancel-button${showCopyright ? ' cancel-button-with-copyright' : ''}`}
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

  const copyrightLabel = showCopyright
    ? COPYRIGHT_LABELS[normalizeCopyright(display.copyright)]
    : null

  return (
    <>
      <div className="score-title">{display.title}</div>
      <div style={{ height: 5 }} />
      <div className="score-composer">{display.composer}</div>
      <div style={{ height: 5 }} />
      <div className="score-publisher">{display.publisher}</div>
      {copyrightLabel ? (
        <>
          <div style={{ height: 5 }} />
          <div className="score-publisher">{copyrightLabel}</div>
        </>
      ) : null}
    </>
  )
}
