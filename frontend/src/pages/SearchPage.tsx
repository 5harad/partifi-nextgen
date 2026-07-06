import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { createPartsetFromScore, getCsrfToken, searchPartsets } from '../lib/api'
import { imslpReverseLookupUrl } from '../lib/imslpUtils'
import type { SearchResultItem } from '../types/search'

const RESULTS_PER_PAGE = 10
const PAGE_WIDTH = 740
const MIN_CARD_HEIGHT = 575

function adjustSerpHeights(pagesContainer: HTMLElement | null): { wrapper: number; main: number } {
  const pageEls = pagesContainer?.querySelectorAll<HTMLElement>('.search-results-page')
  if (!pageEls?.length) {
    return { wrapper: MIN_CARD_HEIGHT + 25, main: MIN_CARD_HEIGHT + 200 }
  }

  let contentHeight = MIN_CARD_HEIGHT
  pageEls.forEach((el) => {
    el.style.height = 'auto'
    contentHeight = Math.max(contentHeight, el.offsetHeight)
  })
  pageEls.forEach((el) => {
    el.style.height = `${contentHeight}px`
  })
  return { wrapper: contentHeight + 25, main: contentHeight + 200 }
}

function chunkResults(results: SearchResultItem[]): SearchResultItem[][] {
  const pages: SearchResultItem[][] = []
  for (let i = 0; i < results.length; i += RESULTS_PER_PAGE) {
    pages.push(results.slice(i, i + RESULTS_PER_PAGE))
  }
  return pages
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const urlQuery = searchParams.get('q') ?? ''
  const [query, setQuery] = useState(urlQuery)
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [pageIndex, setPageIndex] = useState(0)
  const [cloning, setCloning] = useState(false)
  const pagesContainerRef = useRef<HTMLDivElement>(null)
  const [serpHeights, setSerpHeights] = useState({
    wrapper: MIN_CARD_HEIGHT + 25,
    main: MIN_CARD_HEIGHT + 200,
  })

  const pages = useMemo(() => chunkResults(results), [results])

  useEffect(() => {
    setQuery(urlQuery)
  }, [urlQuery])

  const runSearch = useCallback(async (term: string) => {
    setLoading(true)
    setSearchError(null)
    try {
      const data = await searchPartsets(term)
      setResults(data.results)
      setPageIndex(0)
    } catch (err) {
      setResults([])
      setPageIndex(0)
      setSearchError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = query.trim()
      if (next !== (searchParams.get('q') ?? '')) {
        setSearchParams(next ? { q: next } : {}, { replace: true })
      }
      void runSearch(next)
    }, 500)
    return () => window.clearTimeout(timer)
  }, [query, runSearch, searchParams, setSearchParams])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const active = document.activeElement
      if (active instanceof HTMLInputElement && active.id === 'query-field') return
      if (e.key === 'ArrowLeft' && pageIndex > 0) {
        setPageIndex((p) => p - 1)
      } else if (e.key === 'ArrowRight' && pageIndex < pages.length - 1) {
        setPageIndex((p) => p + 1)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [pageIndex, pages.length])

  useEffect(() => {
    const run = () => setSerpHeights(adjustSerpHeights(pagesContainerRef.current))
    run()
    const timer = window.setTimeout(run, 500)
    return () => window.clearTimeout(timer)
  }, [pages, loading, searchError, query, results])

  const handlePartifi = async (result: SearchResultItem) => {
    if (!result.title || !result.composer) return
    setCloning(true)
    try {
      const csrf = await getCsrfToken()
      const created = await createPartsetFromScore(
        {
          score_id: result.score_id,
          title: result.title,
          composer: result.composer,
          publisher: result.publisher ?? '',
          copyright: 'before 1923',
        },
        csrf,
      )
      navigate(`/${created.id}/segment`)
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to prepare score')
      setCloning(false)
    }
  }

  if (cloning) {
    return (
      <div id="transition-wrapper">
        <img
          src="/images/notes_bg.jpg"
          width={1190}
          height={252}
          style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
          alt=""
        />
        <div id="transition">
          <div id="transition-text" style={{ top: 120 }}>
            Please wait while we prepare the score
          </div>
        </div>
      </div>
    )
  }

  return (
    <Layout>
      <div id="main" style={{ height: serpHeights.main }}>
        <img
          src="/images/notes_bg.jpg"
          width={1190}
          height={252}
          style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
          alt=""
        />
        <div id="search-box">
          <div id="query-field-wrapper">
            <input
              id="query-field"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
              placeholder="search for music"
            />
            <div>Enter your search query in the box</div>
          </div>
        </div>

        {pageIndex > 0 && (
          <div
            id="left-serp-nav"
            role="button"
            tabIndex={0}
            onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
            onKeyDown={() => {}}
          />
        )}
        {pageIndex < pages.length - 1 && pages.length > 0 && (
          <div
            id="right-serp-nav"
            role="button"
            tabIndex={0}
            onClick={() => setPageIndex((p) => Math.min(pages.length - 1, p + 1))}
            onKeyDown={() => {}}
          />
        )}

        <div
          id="search-results-wrapper"
          ref={pagesContainerRef}
          style={{ zIndex: 1, height: serpHeights.wrapper }}
        >
          <div
            id="search-results-pages"
            style={{
              position: 'absolute',
              top: 0,
              left: `${-pageIndex * PAGE_WIDTH}px`,
              transition: 'left 0.2s ease',
            }}
          >
            {loading && results.length === 0 && query.trim() && (
              <div className="search-results-page" style={{ left: 0 }}>
                <div className="box-top" />
                <div className="search-results">
                  <p id="search-no-results">Searching…</p>
                </div>
                <div className="box-bottom" />
              </div>
            )}
            {!loading && results.length === 0 && !query.trim() && (
              <div className="search-results-page" style={{ left: 0 }}>
                <div className="box-top" />
                <div className="search-results">
                  <p id="search-no-results">Enter your search query above</p>
                </div>
                <div className="box-bottom" />
              </div>
            )}
            {!loading && searchError && (
              <div className="search-results-page" style={{ left: 0 }}>
                <div className="box-top" />
                <div className="search-results">
                  <p id="search-no-results" className="red">
                    {searchError}
                  </p>
                </div>
                <div className="box-bottom" />
              </div>
            )}
            {!loading && results.length === 0 && query.trim() && !searchError && (
              <div className="search-results-page" style={{ left: 0 }}>
                <div className="box-top" />
                <div className="search-results">
                  <p id="search-no-results">Your query did not return any results</p>
                </div>
                <div className="box-bottom" />
              </div>
            )}
            {pages.map((pageResults, pageNum) => (
              <div
                key={pageNum}
                className="search-results-page"
                style={{ left: `${pageNum * PAGE_WIDTH}px` }}
              >
                <div className="box-top" />
                <div className="search-results">
                  {pageResults.map((result, idx) => (
                    <div
                      key={`${result.score_id}-${pageNum}-${idx}`}
                      className="serp-result"
                      style={
                        idx === pageResults.length - 1 ? { border: 'none' } : undefined
                      }
                    >
                      <div className="serp-result-title">{result.title}</div>
                      <div className="serp-result-composer">{result.composer}</div>
                      <div className="serp-result-publisher">{result.publisher}</div>
                      <div>
                        <a className="red" href={result.score_pdf_url}>
                          download
                        </a>
                        {result.imslp_id && (
                          <>
                            {' | '}
                            <a
                              className="red"
                              href={imslpReverseLookupUrl(result.imslp_id)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              imslp
                            </a>
                          </>
                        )}
                        {' | '}
                        <a
                          href="#"
                          className="red search-results-partifi"
                          onClick={(e) => {
                            e.preventDefault()
                            void handlePartifi(result)
                          }}
                        >
                          partifi
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="box-bottom" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
