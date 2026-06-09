import { useState } from 'react'
import { Layout } from '../components/Layout'

export function HomePage() {
  const [importMode, setImportMode] = useState<'pdf' | 'imslp'>('pdf')

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
          <form id="pdf-form" onSubmit={(e) => e.preventDefault()}>
            <div id="score-field" className="score-input-label">
              score<span className="asterisk">*</span>
              <input type="text" name="filename" id="filename" readOnly />
              <div id="file-select">Select file</div>
              <input type="file" id="file-elem" name="score" style={{ visibility: 'hidden' }} />
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
            <div id="pdf-submit" className="banner-button import-next-button">
              Import score &raquo;
            </div>
          </form>
        ) : (
          <form id="imslp-form" onSubmit={(e) => e.preventDefault()}>
            <div id="imslp-field" className="score-input-label">
              imslp id<span className="asterisk">*</span>
              <input type="text" id="imslp_id" />
            </div>
            <div className="score-input-label title-field">
              title<span className="asterisk">*</span>
              <input type="text" className="score-input" id="imslp_title" />
            </div>
            <div className="score-input-label composer-field">
              composer<span className="asterisk">*</span>
              <input type="text" className="score-input" id="imslp_composer" />
            </div>
            <div className="score-input-label publisher-field">
              edition &nbsp;
              <input type="text" className="score-input" id="imslp_publisher" />
            </div>
            <div className="copyright-tip" />
            <div className="copyright">
              copyright<span className="asterisk">*</span>
            </div>
            <div className="copyright-options">
              <select id="imslp_copyright" defaultValue="">
                <option value="" />
                <option value="before 1923">Published before 1923</option>
                <option value="after 1923">Published in or after 1923</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div id="imslp-submit" className="banner-button import-next-button">
              Import score &raquo;
            </div>
          </form>
        )}
      </div>
    </Layout>
  )
}
