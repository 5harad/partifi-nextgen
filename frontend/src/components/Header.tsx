import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { GoogleSignInLink } from './GoogleSignInLink'

const PLACEHOLDER = 'search for music'

export function Header() {
  const navigate = useNavigate()
  const {
    user,
    loading,
    googleEnabled,
    loginWithGoogle,
    logout,
  } = useAuth()

  const firstName = user?.name?.split(' ')[0] ?? 'there'

  return (
    <div id="header">
      <Link id="logo-link" to="/">
        <img src="/images/partifi_logo.gif" style={{ border: 'none' }} alt="Partifi" />
      </Link>
      <input
        type="text"
        id="searchbox"
        defaultValue={PLACEHOLDER}
        onFocus={(e) => {
          if (e.currentTarget.value === PLACEHOLDER) e.currentTarget.value = ''
        }}
        onBlur={(e) => {
          if (!e.currentTarget.value.trim()) e.currentTarget.value = PLACEHOLDER
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            const q = e.currentTarget.value.trim()
            if (q && q !== PLACEHOLDER) {
              navigate(`/search?q=${encodeURIComponent(q)}`)
            }
          }
        }}
      />
      <div id="login">
        {!loading && user && (
          <>
            <span style={{ color: 'white' }}>Hi, {firstName}</span>
            <a
              href="#"
              style={{ marginLeft: 15 }}
              onClick={(e) => {
                e.preventDefault()
                void logout()
              }}
            >
              Sign Out
            </a>
            <Link to="/library" style={{ marginLeft: 15 }}>
              My Library
            </Link>
          </>
        )}
        {!loading && !user && googleEnabled && (
          <GoogleSignInLink onLogin={loginWithGoogle} style={{ marginLeft: 15 }} />
        )}
        <Link to="/howto" style={{ marginLeft: 15 }}>
          Help
        </Link>
        <Link to="/faq" style={{ marginLeft: 15 }}>
          FAQ
        </Link>
      </div>
    </div>
  )
}
