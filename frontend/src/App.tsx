import { Route, Routes } from 'react-router-dom'
import { AboutPage } from './pages/AboutPage'
import { HomePage } from './pages/HomePage'
import { HowToPage } from './pages/HowToPage'
import { ImportProgressPage } from './pages/ImportProgressPage'
import { PartgenProgressPage } from './pages/PartgenProgressPage'
import { PartsPage } from './pages/PartsPage'
import { PreviewPage } from './pages/PreviewPage'
import { SegmentPage } from './pages/SegmentPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/howto" element={<HowToPage />} />
      <Route path="/:privateId/import" element={<ImportProgressPage />} />
      <Route path="/:privateId/segment" element={<SegmentPage />} />
      <Route path="/:privateId/preview" element={<PreviewPage />} />
      <Route path="/:privateId/partgen" element={<PartgenProgressPage />} />
      <Route path="/:privateId/parts" element={<PartsPage />} />
    </Routes>
  )
}

export default App
