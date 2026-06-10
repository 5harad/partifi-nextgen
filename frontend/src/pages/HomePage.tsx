import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { createPartsetFromImslp, createPartsetFromPdf, getCsrfToken, getImslpInfo, sha1File } from '../lib/api'
import { guessCopyrightFromPublisher, normalizeImslpIdInput } from '../lib/imslpUtils'
import type { CopyrightValue } from '../lib/imslpUtils'

export function HomePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [importMode, setImportMode] = useState<'pdf' | 'imslp'>('pdf')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [filename, setFilename] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(searchParams.get('err') || '')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [imslpId, setImslpId] = useState('')
  const [imslpTitle, setImslpTitle] = useState('')
  const [imslpComposer, setImslpComposer] = useState('')
  const [imslpPublisher, setImslpPublisher] = useState('')
  const [imslpCopyright, setImslpCopyright] = useState<CopyrightValue | ''>('')
  const [imslpLookupPending, setImslpLookupPending] = useState(false)
  const lookupGenRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)

  const MIN_IMSLP_ID_LENGTH = 4

  const openFilePicker = () => fileInputRef.current?.click()

  const handleFileChange = async (file: File | undefined) => {
    setError('')
    if (!file) {
      setSelectedFile(null)
      setFilename('')
      return
    }

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a PDF file.')
      return
    }
    if (file.size > 60_000_000) {
      setError('Please select a file no larger than 60 MB.')
      return
    }

    setSelectedFile(file)
    setFilename(file.name)
  }

  const lookupImslp = useCallback(async (rawId: string) => {
    const normalized = normalizeImslpIdInput(rawId)

    abortRef.current?.abort()
    abortRef.current = null

    if (!normalized || !/^\d+$/.test(normalized)) {
      setImslpLookupPending(false)
      setImslpTitle('')
      setImslpComposer('')
      setImslpPublisher('')
      setImslpCopyright('')
      return
    }

    if (normalized.length < MIN_IMSLP_ID_LENGTH) {
      setImslpLookupPending(false)
      return
    }

    const controller = new AbortController()
    abortRef.current = controller
    const gen = ++lookupGenRef.current
    setImslpLookupPending(true)
    setImslpTitle('')
    setImslpComposer('')
    setImslpPublisher('')
    setImslpCopyright('')

    try {
      const info = await getImslpInfo(normalized, controller.signal)
      if (gen !== lookupGenRef.current) return
      if (!info) {
        setError('IMSLP score not found or not a PDF.')
        return
      }
      setError('')
      setImslpTitle(info.title)
      setImslpComposer(info.composer)
      setImslpPublisher(info.publisher)
      const guessed = guessCopyrightFromPublisher(info.publisher)
      if (guessed) {
        setImslpCopyright(guessed)
      } else if (info.title) {
        setImslpCopyright('unknown')
      }
    } catch (err) {
      if (gen !== lookupGenRef.current || controller.signal.aborted) return
      setError(err instanceof Error ? err.message : 'IMSLP lookup failed')
    } finally {
      if (gen === lookupGenRef.current) {
        setImslpLookupPending(false)
        abortRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    const param = searchParams.get('imslp')
    if (param && /^\d+$/.test(param)) {
      setImportMode('imslp')
      setImslpId(param)
    }
  }, [searchParams])

  useEffect(() => {
    if (importMode !== 'imslp') return
    const timer = window.setTimeout(() => {
      void lookupImslp(imslpId)
    }, 600)
    return () => window.clearTimeout(timer)
  }, [imslpId, importMode, lookupImslp])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  const handlePdfSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const title = (document.getElementById('pdf_title') as HTMLInputElement).value.trim()
    const composer = (document.getElementById('pdf_composer') as HTMLInputElement).value.trim()
    const publisher = (document.getElementById('pdf_publisher') as HTMLInputElement).value.trim()
    const copyright = (document.getElementById('pdf_copyright') as HTMLSelectElement).value

    if (!selectedFile || !filename || !title || !composer || !copyright) {
      setError('Please complete the form before continuing.')
      return
    }

    setSubmitting(true)
    try {
      const [csrfToken, fileHash] = await Promise.all([getCsrfToken(), sha1File(selectedFile)])
      const result = await createPartsetFromPdf({
        file: selectedFile,
        title,
        composer,
        publisher,
        copyright,
        fileHash,
        csrfToken,
      })
      navigate(`/${result.id}/import`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setSubmitting(false)
    }
  }

  const handleImslpSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const normalized = normalizeImslpIdInput(imslpId)
    if (!normalized || !imslpTitle || !imslpComposer || !imslpCopyright) {
      setError('Please complete the form before continuing.')
      return
    }

    setSubmitting(true)
    try {
      const csrfToken = await getCsrfToken()
      const result = await createPartsetFromImslp(
        {
          imslp_id: normalized,
          title: imslpTitle,
          composer: imslpComposer,
          publisher: imslpPublisher,
          copyright: imslpCopyright,
        },
        csrfToken,
      )
      navigate(`/${result.id}/import`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
      setSubmitting(false)
    }
  }

  return (
    <Layout>
      <div id="main" style={{ height: '750px' }}>
        <div id="main-tag-text">An automated tool for creating parts from music scores</div>
        <img
          src="/images/notes_bg.jpg"
          width={1190}
          height={252}
          style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
          alt=""
        />
        <img src="/images/musicstand.gif" height={640} width={774} alt="" />

        {error && (
          <div style={{ color: '#ff9999', padding: '10px 40px' }}>{error}</div>
        )}

        <div id="step">STEP 1. &nbsp; Import sheet music</div>

        <div
          id="pdf-import"
          className={`import-button ${importMode === 'pdf' ? 'import-button-down' : ''}`}
          onClick={() => setImportMode('pdf')}
          role="button"
          tabIndex={0}
        >
          <img src="/images/pdf.gif" style={{ position: 'relative', top: 3, marginRight: 8 }} alt="" />
          .pdf
        </div>
        <div
          id="imslp-import"
          className={`import-button ${importMode === 'imslp' ? 'import-button-down' : ''}`}
          onClick={() => setImportMode('imslp')}
          role="button"
          tabIndex={0}
        >
          <img src="/images/db_icon.gif" style={{ position: 'relative', top: 3, marginRight: 3 }} alt="" />
          {' '}
          imslp library
        </div>

        {importMode === 'pdf' ? (
          <form id="pdf-form" onSubmit={handlePdfSubmit}>
            <div id="score-field" className="score-input-label">
              score<span className="asterisk">*</span>
              <input type="text" name="filename" id="filename" readOnly value={filename} />
              <div id="file-select" onClick={openFilePicker} role="button" tabIndex={0}>
                Select file
              </div>
              <input
                ref={fileInputRef}
                type="file"
                id="file-elem"
                name="score"
                accept="application/pdf,.pdf"
                style={{ visibility: 'hidden' }}
                onChange={(e) => handleFileChange(e.target.files?.[0])}
              />
            </div>
            <div className="score-input-label title-field">
              title<span className="asterisk">*</span>
              <input type="text" className="score-input" id="pdf_title" />
            </div>
            <div className="score-input-label composer-field">
              composer<span className="asterisk">*</span>
              <input type="text" className="score-input" id="pdf_composer" />
            </div>
            <div className="score-input-label publisher-field">
              edition &nbsp;
              <input type="text" className="score-input" id="pdf_publisher" />
            </div>
            <div className="copyright-tip" />
            <div className="copyright">
              copyright<span className="asterisk">*</span>
            </div>
            <div className="copyright-options">
              <select id="pdf_copyright" defaultValue="">
                <option value="" />
                <option value="before 1923">Published before 1923</option>
                <option value="after 1923">Published in or after 1923</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div
              id="pdf-submit"
              className="banner-button import-next-button"
              onClick={submitting ? undefined : handlePdfSubmit}
              role="button"
              tabIndex={0}
              style={{ opacity: submitting ? 0.6 : 1 }}
            >
              {submitting ? 'Uploading...' : 'Import score »'}
            </div>
          </form>
        ) : (
          <form id="imslp-form" onSubmit={handleImslpSubmit}>
            <div id="imslp-field" className="score-input-label">
              imslp id<span className="asterisk">*</span>
              <input
                type="text"
                id="imslp_id"
                value={imslpId}
                onChange={(e) => setImslpId(e.target.value)}
              />
            </div>
            <div className="score-input-label title-field">
              title<span className="asterisk">*</span>
              <input
                type="text"
                className="score-input"
                id="imslp_title"
                value={imslpTitle}
                onChange={(e) => setImslpTitle(e.target.value)}
              />
            </div>
            <div className="score-input-label composer-field">
              composer<span className="asterisk">*</span>
              <input
                type="text"
                className="score-input"
                id="imslp_composer"
                value={imslpComposer}
                onChange={(e) => setImslpComposer(e.target.value)}
              />
            </div>
            <div className="score-input-label publisher-field">
              edition &nbsp;
              <input
                type="text"
                className="score-input"
                id="imslp_publisher"
                value={imslpPublisher}
                onChange={(e) => setImslpPublisher(e.target.value)}
              />
            </div>
            <div className="copyright-tip" />
            <div className="copyright">
              copyright<span className="asterisk">*</span>
            </div>
            <div className="copyright-options">
              <select
                id="imslp_copyright"
                value={imslpCopyright}
                onChange={(e) => setImslpCopyright(e.target.value as CopyrightValue | '')}
              >
                <option value="" />
                <option value="before 1923">Published before 1923</option>
                <option value="after 1923">Published in or after 1923</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div
              id="imslp-submit"
              className="banner-button import-next-button"
              onClick={submitting || imslpLookupPending ? undefined : handleImslpSubmit}
              role="button"
              tabIndex={0}
              style={{ opacity: submitting || imslpLookupPending ? 0.6 : 1 }}
            >
              {submitting ? 'Importing...' : imslpLookupPending ? 'Looking up…' : 'Import score »'}
            </div>
          </form>
        )}
      </div>
    </Layout>
  )
}
