import { useLayoutEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { AboutPage } from './pages/AboutPage'
import { FaqPage } from './pages/FaqPage'
import { PrivacyPage } from './pages/PrivacyPage'
import { TermsPage } from './pages/TermsPage'
import { HomePage } from './pages/HomePage'
import { HowToPage } from './pages/HowToPage'
import { ImportProgressPage } from './pages/ImportProgressPage'
import { LibraryPage } from './pages/LibraryPage'
import { OrientationPage } from './pages/OrientationPage'
import { PartgenProgressPage } from './pages/PartgenProgressPage'
import { PartsPage } from './pages/PartsPage'
import { PreviewPage } from './pages/PreviewPage'
import { SearchPage } from './pages/SearchPage'
import { SegmentPage } from './pages/SegmentPage'

function ScrollToTop() {
  const { pathname, hash } = useLocation()

  useLayoutEffect(() => {
    if (!hash) window.scrollTo(0, 0)
  }, [pathname, hash])

  return null
}

function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/howto" element={<HowToPage />} />
        <Route path="/faq" element={<FaqPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/:privateId/import" element={<ImportProgressPage />} />
        <Route path="/:privateId/segment" element={<SegmentPage />} />
        <Route path="/:privateId/orientation" element={<OrientationPage />} />
        <Route path="/:privateId/preview" element={<PreviewPage />} />
        <Route path="/:privateId/partgen" element={<PartgenProgressPage />} />
        <Route path="/:accessId" element={<PartsPage />} />
      </Routes>
    </>
  )
}

export default App
