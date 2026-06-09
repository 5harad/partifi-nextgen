import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const PLACEHOLDER = 'search for music'

export function Header() {
  const navigate = useNavigate()
  const [searchValue, setSearchValue] = useState(PLACEHOLDER)

  return (
    <div id="header">
      <Link id="logo-link" to="/">
        <img src="/images/partifi_logo.gif" style={{ border: 'none' }} alt="Partifi" />
      </Link>
      <input
        type="text"
        id="searchbox"
        value={searchValue}
        onFocus={() => {
          if (searchValue === PLACEHOLDER) setSearchValue('')
        }}
        onBlur={() => {
          if (!searchValue.trim()) setSearchValue(PLACEHOLDER)
        }}
        onChange={(e) => setSearchValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            const q = searchValue.trim()
            if (q && q !== PLACEHOLDER) {
              navigate(`/search?q=${encodeURIComponent(q)}`)
            }
          }
        }}
      />
      <div id="login">
        <Link to="/howto" style={{ marginLeft: 15 }}>
          Help
        </Link>
      </div>
    </div>
  )
}
