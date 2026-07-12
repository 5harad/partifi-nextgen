import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { GoogleSignInLink } from './GoogleSignInLink'
import { displayGreetingName } from '../lib/greetingName'

const PLACEHOLDER = 'search for music'
const HEADER_PREVIEW_NAMES: Record<string, string> = {
  'long-name': 'Kathrine Brandt Soprano',
  'extra-long-name':
    'Kathrine Brandt Soprano Associate Concertmaster and Principal Artist Laureate Emeritus',
}

function headerPreviewName(param: string | null): string | null {
  if (!param) return null
  return HEADER_PREVIEW_NAMES[param] ?? param
}

export function Header() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const previewName = import.meta.env.DEV
    ? headerPreviewName(searchParams.get('headerPreview'))
    : null
  const devLongNamePreview = previewName !== null
  const {
    user,
    loading,
    googleEnabled,
    loginWithGoogleCode,
    logout,
  } = useAuth()

  const showLoggedIn = devLongNamePreview || (!loading && Boolean(user))
  const firstName = devLongNamePreview
    ? previewName
    : displayGreetingName(user?.given_name, user?.name)

  return (
    <div id="header">
      <div id="header-inner">
        <Link id="logo-link" to="/">
          <img src="/images/partifi_logo.gif" style={{ border: 'none' }} alt="Partifi" />
        </Link>
        <div id="login">
          {showLoggedIn && (
            <span className="header-greeting">Hi, {firstName}</span>
          )}
          <div className="header-nav-links">
            {showLoggedIn && (
              <>
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault()
                    if (devLongNamePreview) return
                    void logout()
                  }}
                >
                  Sign Out
                </a>
                <Link to="/library">My Library</Link>
              </>
            )}
            {!showLoggedIn && !loading && googleEnabled && (
              <GoogleSignInLink onLogin={loginWithGoogleCode} />
            )}
            <Link to="/howto">Help</Link>
            <Link to="/faq">FAQ</Link>
          </div>
        </div>
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
      </div>
    </div>
  )
}
