import { Route, Routes } from 'react-router-dom'
import { AboutPage } from './pages/AboutPage'
import { HomePage } from './pages/HomePage'
import { HowToPage } from './pages/HowToPage'
import { ImportProgressPage } from './pages/ImportProgressPage'
import { SegmentPage } from './pages/SegmentPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/howto" element={<HowToPage />} />
      <Route path="/:privateId/import" element={<ImportProgressPage />} />
      <Route path="/:privateId/segment" element={<SegmentPage />} />
    </Routes>
  )
}

export default App
