import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { ComposerInput } from '../components/ComposerInput'
import { CopyrightTip } from '../components/CopyrightTip'
import { createPartsetFromImslp, createPartsetFromPdf, getCsrfToken, getImslpInfo, sha1File } from '../lib/api'
import { guessCopyrightFromPublisher, normalizeImslpIdInput } from '../lib/imslpUtils'
import { pipelineErrorMessage } from '../lib/pipelineErrors'
import { MAX_SCORE_BYTES, scoreTooLargeMessage } from '../lib/scoreLimits'
import type { CopyrightValue } from '../lib/imslpUtils'

export function HomePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [importMode, setImportMode] = useState<'pdf' | 'imslp'>('pdf')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [filename, setFilename] = useState('')
  const [pdfTitle, setPdfTitle] = useState('')
  const [pdfComposer, setPdfComposer] = useState('')
  const [pdfPublisher, setPdfPublisher] = useState('')
  const [pdfCopyright, setPdfCopyright] = useState<CopyrightValue | ''>('')
  const [submitting, setSubmitting] = useState(false)
  const [pdfError, setPdfError] = useState(() => {
    const err = searchParams.get('err')
    return err ? pipelineErrorMessage(err) : ''
  })
  const [imslpError, setImslpError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [imslpId, setImslpId] = useState('')
  const [imslpTitle, setImslpTitle] = useState('')
  const [imslpComposer, setImslpComposer] = useState('')
  const [imslpPublisher, setImslpPublisher] = useState('')
  const [imslpCopyright, setImslpCopyright] = useState<CopyrightValue | ''>('')
  const [imslpLookupPending, setImslpLookupPending] = useState(false)
  const [pdfDropActive, setPdfDropActive] = useState(false)
  const lookupGenRef = useRef(0)
  const suppressNextLookupRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)
  const pdfDropZoneRef = useRef<HTMLDivElement>(null)
  const pdfDropActiveRef = useRef(false)

  const MIN_IMSLP_ID_LENGTH = 4

  const openFilePicker = () => fileInputRef.current?.click()

  const handleFileChange = async (file: File | undefined) => {
    setPdfError('')
    if (!file) {
      setSelectedFile(null)
      setFilename('')
      return
    }

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setPdfError('Please select a PDF file.')
      return
    }
    if (file.size > MAX_SCORE_BYTES) {
      setPdfError(scoreTooLargeMessage(file.size))
      return
    }

    setSelectedFile(file)
    setFilename(file.name)
  }

  const setPdfDropActiveBoth = (active: boolean) => {
    pdfDropActiveRef.current = active
    setPdfDropActive(active)
  }

  const pointInPdfDropZone = (clientX: number, clientY: number) => {
    const zone = pdfDropZoneRef.current
    if (!zone) return false
    const rect = zone.getBoundingClientRect()
    return (
      clientX >= rect.left &&
      clientX <= rect.right &&
      clientY >= rect.top &&
      clientY <= rect.bottom
    )
  }

  // Hit-test the same rectangle as the overlay (zone is visual-only; pointer-events: none).
  useEffect(() => {
    setPdfDropActiveBoth(false)

    const hasFiles = (dt: DataTransfer | null) => {
      if (!dt) return false
      // On drop, some browsers expose files but leave types empty — check both.
      if (dt.files?.length) return true
      return [...dt.types].includes('Files')
    }

    const onDragOver = (e: DragEvent) => {
      if (!hasFiles(e.dataTransfer)) return
      // Must cancel dragover on the page or the browser will navigate on drop.
      // Keep dropEffect 'copy' (not 'none') — 'none' made in-zone drops feel laggy.
      e.preventDefault()
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
      if (importMode !== 'pdf') {
        if (pdfDropActiveRef.current) setPdfDropActiveBoth(false)
        return
      }
      const inside = pointInPdfDropZone(e.clientX, e.clientY)
      if (inside !== pdfDropActiveRef.current) {
        setPdfDropActiveBoth(inside)
      }
    }

    const onDrop = (e: DragEvent) => {
      if (!hasFiles(e.dataTransfer)) return
      e.preventDefault()
      setPdfDropActiveBoth(false)
      if (importMode !== 'pdf') return
      if (!pointInPdfDropZone(e.clientX, e.clientY)) return
      const file = e.dataTransfer?.files?.[0]
      void handleFileChange(file)
    }

    const onDragEnd = () => setPdfDropActiveBoth(false)

    window.addEventListener('dragover', onDragOver)
    window.addEventListener('drop', onDrop)
    window.addEventListener('dragend', onDragEnd)
    return () => {
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('drop', onDrop)
      window.removeEventListener('dragend', onDragEnd)
    }
    // handleFileChange is stable enough for this effect; zone ref is read live.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importMode])

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
    setImslpError('')
    setImslpTitle('')
    setImslpComposer('')
    setImslpPublisher('')
    setImslpCopyright('')

    try {
      const info = await getImslpInfo(normalized, controller.signal)
      if (gen !== lookupGenRef.current) return
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
      setImslpError(err instanceof Error ? err.message : 'IMSLP lookup failed')
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
    if (importMode !== 'imslp' || submitting) return
    if (suppressNextLookupRef.current) {
      suppressNextLookupRef.current = false
      return
    }
    const timer = window.setTimeout(() => {
      void lookupImslp(imslpId)
    }, 600)
    return () => window.clearTimeout(timer)
  }, [imslpId, importMode, lookupImslp, submitting])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  const handlePdfSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const pendingFile = fileInputRef.current?.files?.[0]
    if (pendingFile && pendingFile.size > MAX_SCORE_BYTES) {
      setPdfError(scoreTooLargeMessage(pendingFile.size))
      return
    }

    const title = pdfTitle.trim()
    const composer = pdfComposer.trim()
    const publisher = pdfPublisher.trim()
    const copyright = pdfCopyright

    if (!selectedFile || !filename || !title || !composer || !copyright) {
      setPdfError('Please complete the form before continuing.')
      return
    }

    if (selectedFile.size > MAX_SCORE_BYTES) {
      setPdfError(scoreTooLargeMessage(selectedFile.size))
      return
    }

    setPdfError('')

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
      setPdfError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setSubmitting(false)
    }
  }

  const handleImslpSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const normalized = normalizeImslpIdInput(imslpId.trim())
    const title = imslpTitle.trim()
    const composer = imslpComposer.trim()
    const publisher = imslpPublisher.trim()
    const copyright = imslpCopyright

    if (!normalized || !title || !composer || !copyright) {
      setImslpError('Please complete the form before continuing.')
      return
    }

    abortRef.current?.abort()
    abortRef.current = null
    setImslpLookupPending(false)
    setImslpError('')
    setSubmitting(true)
    try {
      const csrfToken = await getCsrfToken()
      const result = await createPartsetFromImslp(
        {
          imslp_id: normalized,
          title,
          composer,
          publisher,
          copyright,
        },
        csrfToken,
      )
      navigate(`/${result.id}/import`)
    } catch (err) {
      suppressNextLookupRef.current = true
      setImslpError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Layout>
      <div className="site-canvas site-canvas--long-pole">
        <div className="stand-stage">
        <div id="main" className="canvas-page">
        <div id="main-tag-text">An automated tool for creating parts from music scores</div>
        <img
          src="/images/notes_bg.jpg"
          width={1190}
          height={252}
          style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
          alt=""
        />
        <img className="stand-figure-img" src="/images/musicstand-long.gif" width={774} alt="" />

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
            <div
              ref={pdfDropZoneRef}
              id="pdf-drop-zone"
              className={pdfDropActive ? 'pdf-drop-active' : undefined}
              aria-hidden={!pdfDropActive}
            >
              <div className="pdf-drop-overlay-card">
                <img src="/images/pdf.gif" alt="" width={28} height={28} />
                <span>Drop PDF here</span>
              </div>
            </div>
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
              <input
                type="text"
                className="score-input"
                id="pdf_title"
                value={pdfTitle}
                onChange={(e) => setPdfTitle(e.target.value)}
              />
            </div>
            <div className="score-input-label composer-field">
              composer<span className="asterisk">*</span>
              <ComposerInput
                id="pdf_composer"
                className="score-input"
                value={pdfComposer}
                onChange={setPdfComposer}
              />
            </div>
            <div className="score-input-label publisher-field">
              edition &nbsp;
              <input
                type="text"
                className="score-input"
                id="pdf_publisher"
                value={pdfPublisher}
                onChange={(e) => setPdfPublisher(e.target.value)}
              />
            </div>
            <CopyrightTip />
            <div className="copyright">
              copyright<span className="asterisk">*</span>
            </div>
            <div className="copyright-options">
              <select
                id="pdf_copyright"
                value={pdfCopyright}
                onChange={(e) => setPdfCopyright(e.target.value as CopyrightValue | '')}
              >
                <option value="" />
                <option value="before 1923">Published before 1923</option>
                <option value="after 1923">Published in or after 1923</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div className="import-action">
              {pdfError ? (
                <div id="import-error" role="alert">
                  {pdfError}
                </div>
              ) : null}
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
            </div>
          </form>
        ) : (
          <form id="imslp-form" onSubmit={handleImslpSubmit}>
            <div id="imslp-field" className="score-input-label">
              imslp id<span className="asterisk">*</span>
              <input
                type="text"
                id="imslp_id"
                inputMode="numeric"
                pattern="[0-9]*"
                value={imslpId}
                onChange={(e) => setImslpId(e.target.value.replace(/\D/g, ''))}
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
            <CopyrightTip />
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
            <div className="import-action">
              {imslpError ? (
                <div id="import-error" role="alert">
                  {imslpError}
                </div>
              ) : null}
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
            </div>
          </form>
        )}
        </div>
        </div>
        <div className="site-canvas-seam" aria-hidden="true" />
        <div className="site-canvas-fill" aria-hidden="true" />
      </div>
    </Layout>
  )
}
