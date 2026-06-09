import { Route, Routes } from 'react-router-dom'
import { AboutPage } from './pages/AboutPage'
import { HomePage } from './pages/HomePage'
import { HowToPage } from './pages/HowToPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/howto" element={<HowToPage />} />
    </Routes>
  )
}

export default App
