import { Route, Routes } from 'react-router-dom'
import { AboutPage } from './pages/AboutPage'
import { TermsPage } from './pages/TermsPage'
import { HomePage } from './pages/HomePage'
import { HowToPage } from './pages/HowToPage'
import { ImportProgressPage } from './pages/ImportProgressPage'
import { LibraryPage } from './pages/LibraryPage'
import { PartgenProgressPage } from './pages/PartgenProgressPage'
import { PartsPage } from './pages/PartsPage'
import { PreviewPage } from './pages/PreviewPage'
import { SearchPage } from './pages/SearchPage'
import { SegmentPage } from './pages/SegmentPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/howto" element={<HowToPage />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="/library" element={<LibraryPage />} />
      <Route path="/:privateId/import" element={<ImportProgressPage />} />
      <Route path="/:privateId/segment" element={<SegmentPage />} />
      <Route path="/:privateId/preview" element={<PreviewPage />} />
      <Route path="/:privateId/partgen" element={<PartgenProgressPage />} />
      <Route path="/:privateId/parts" element={<PartsPage />} />
      <Route path="/:accessId" element={<PartsPage />} />
    </Routes>
  )
}

export default App
