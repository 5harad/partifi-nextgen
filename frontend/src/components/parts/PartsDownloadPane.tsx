import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  deletePartset,
  ensurePartsByAccessId,
  getCsrfToken,
  getPartgenStatusByAccessId,
  getPartsByAccessId,
  retryPartsetPipelineByAccessId,
  updatePartsetMetadata,
} from '../../lib/api'
import { fetchFavoriteStatus, updateFavorite } from '../../lib/authApi'
import { useAuth } from '../../context/AuthContext'
import { pipelineErrorMessage, LOCK_BUSY_MESSAGE } from '../../lib/pipelineErrors'
import { PartsetMetadata, usePartsetMetadata } from '../PartsetMetadata'
import { GoogleSignInLink } from '../GoogleSignInLink'
import { PartDownloadLinks } from './PartDownloadLinks'
import { PartsetShareLinks } from './PartsetShareLinks'
import { ScoreSourceLinks } from './ScoreSourceLinks'
import type { PartsDataResponse } from '../../types/preview'

type Props = {
  data: PartsDataResponse
  onDataChange: React.Dispatch<React.SetStateAction<PartsDataResponse>>
}

export function PartsDownloadPane({ data, onDataChange }: Props) {
  const { user, googleEnabled, loginWithGoogleCode } = useAuth()
  const isOwner = data.mode === 'owner'
  const privateId = data.private_id ?? ''
  const publicId = data.public_id
  const accessId = isOwner ? privateId : publicId

  const metadata = usePartsetMetadata(data)
  const [display, setDisplay] = useState({
    title: data.title,
    composer: data.composer,
    publisher: data.publisher,
  })
  const [favorite, setFavorite] = useState(false)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    setDisplay({
      title: data.title,
      composer: data.composer,
      publisher: data.publisher,
    })
  }, [data.title, data.composer, data.publisher, data.partset_id])

  useEffect(() => {
    if (!user) {
      setFavorite(false)
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const isFavorite = await fetchFavoriteStatus(accessId)
        if (cancelled) return
        if (isFavorite) {
          setFavorite(true)
          return
        }
        if (isOwner) {
          const added = await updateFavorite(accessId, 'add')
          if (!cancelled) setFavorite(added)
        } else {
          setFavorite(false)
        }
      } catch {
        if (!cancelled) setFavorite(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [user, accessId, isOwner])

  useEffect(() => {
    if (data.parts_ready || data.parts.length === 0 || data.error) return

    let cancelled = false
    let timeoutId: number

    const poll = async () => {
      try {
        await ensurePartsByAccessId(accessId)
        const status = await getPartgenStatusByAccessId(accessId)
        if (cancelled) return
        if (status.error) {
          const fresh = await getPartsByAccessId(accessId)
          if (cancelled) return
          onDataChange(fresh)
          return
        }
        if (status.is_complete) {
          const fresh = await getPartsByAccessId(accessId)
          if (cancelled) return
          onDataChange(fresh)
          return
        }
      } catch {
        // Ignore transient polling errors; user can still click a part link.
      }

      if (!cancelled) {
        timeoutId = window.setTimeout(poll, 1000)
      }
    }

    void poll()

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [accessId, data.parts_ready, data.parts.length, data.error, data.partset_id, onDataChange])

  const saveMetadata = useCallback(async () => {
    await metadata.save(async (fields) => {
      const csrf = await getCsrfToken()
      await updatePartsetMetadata(privateId, fields, csrf)
      const next = {
        ...data,
        title: fields.title,
        composer: fields.composer,
        publisher: fields.publisher || null,
      }
      setDisplay({
        title: next.title,
        composer: next.composer,
        publisher: next.publisher,
      })
      onDataChange((prev) => ({
        ...prev,
        title: fields.title,
        composer: fields.composer,
        publisher: fields.publisher || null,
        parts_ready: false,
        error: null,
        error_message: null,
      }))
      try {
        if (data.error) {
          const csrf = await getCsrfToken()
          await retryPartsetPipelineByAccessId(accessId, csrf)
        } else {
          await ensurePartsByAccessId(accessId)
        }
      } catch {
        // Part click or polling will retry ensure-parts.
      }
    })
  }, [metadata, privateId, data, onDataChange, accessId])

  const handleRetry = useCallback(async () => {
    if (!isOwner || retrying) return
    setRetrying(true)
    try {
      const csrf = await getCsrfToken()
      const result = await retryPartsetPipelineByAccessId(accessId, csrf)
      if (result.job_id === null) {
        window.alert(LOCK_BUSY_MESSAGE)
        return
      }
      onDataChange((prev) => ({
        ...prev,
        error: null,
        error_message: null,
        parts_ready: false,
      }))
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not restart part generation.')
    } finally {
      setRetrying(false)
    }
  }, [isOwner, retrying, accessId, onDataChange])

  const handleDelete = useCallback(async () => {
    if (!window.confirm('Are you sure you want to delete these parts?')) return
    try {
      const csrf = await getCsrfToken()
      await deletePartset(privateId, csrf)
      window.location.href = '/'
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to delete partset')
    }
  }, [privateId])

  const toggleFavorite = useCallback(async () => {
    if (!user) {
      window.alert('You must be logged in to add a score to your personal library.')
      return
    }
    try {
      const next = await updateFavorite(accessId, favorite ? 'remove' : 'add')
      setFavorite(next)
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to update your personal library')
    }
  }, [user, accessId, favorite])

  return (
    <div className="download-pane">
      <div className="box-top" />
      {(isOwner || user) && (
        <div className="download-menu">
          {isOwner && (
            <>
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
            </>
          )}
          {user && (
            <>
              {isOwner && ' | '}
              <a href="#" className="red" id="library-link" onClick={(e) => { e.preventDefault(); void toggleFavorite() }}>
                {favorite ? 'remove from my library' : 'add to my library'}
              </a>
            </>
          )}
        </div>
      )}
      {isOwner && !user && (
        <p className="red owner-sign-in-hint">
          {googleEnabled ? (
            <>
              <GoogleSignInLink onLogin={loginWithGoogleCode} className="red">
                Sign in
              </GoogleSignInLink>
              {' '}to save this score to your personal library and return later to edit the parts.
            </>
          ) : (
            'Sign in to save this score to your personal library and return later to edit the parts.'
          )}
        </p>
      )}
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
          errorClassName="red"
        />
      </div>
      <div className="partset-download">
        <div className="download-title">Download</div>
        {data.error && (
          <p className="red partgen-error">
            {pipelineErrorMessage(data.error, data.error_message)}
            {isOwner && (
              <>
                {' '}
                <a
                  href="#"
                  className="red"
                  onClick={(e) => {
                    e.preventDefault()
                    void handleRetry()
                  }}
                >
                  {retrying ? 'Retrying…' : 'Try again'}
                </a>
              </>
            )}
          </p>
        )}
        <ScoreSourceLinks
          scorePdfUrl={data.score_pdf_url}
          imslpId={data.imslp_id}
          scoreDownloadName={`${data.partset_id}_score.pdf`}
        />
        <PartDownloadLinks
          parts={data.parts}
          partsReady={data.parts_ready}
          partgenAccessId={accessId}
        />
      </div>
      <PartsetShareLinks
        isOwner={isOwner}
        privateId={privateId || null}
        publicId={publicId}
      />
      <div className="box-bottom" />
    </div>
  )
}
