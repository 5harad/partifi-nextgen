import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export function Header() {
  const navigate = useNavigate()
  const [searchValue, setSearchValue] = useState('search for music')

  return (
    <div id="header">
      <a id="logo-link" href="/" onClick={(e) => { e.preventDefault(); navigate('/') }}>
        <img src="/images/partifi_logo.gif" style={{ border: 'none' }} alt="Partifi" />
      </a>
      <input
        type="text"
        id="searchbox"
        value={searchValue}
        onFocus={() => {
          if (searchValue === 'search for music') setSearchValue('')
        }}
        onBlur={() => {
          if (!searchValue.trim()) setSearchValue('search for music')
        }}
        onChange={(e) => setSearchValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && searchValue && searchValue !== 'search for music') {
            navigate(`/search?q=${encodeURIComponent(searchValue)}`)
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
