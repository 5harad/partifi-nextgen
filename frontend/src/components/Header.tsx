import { Link } from 'react-router-dom'

export function Header() {
  return (
    <div id="header">
      <Link id="logo-link" to="/">
        <img src="/images/partifi_logo.gif" style={{ border: 'none' }} alt="Partifi" />
      </Link>
      <input
        type="text"
        id="searchbox"
        readOnly
        value="search coming soon"
        title="Public score search is coming in a future release"
      />
      <div id="login">
        <Link to="/howto" style={{ marginLeft: 15 }}>
          Help
        </Link>
      </div>
    </div>
  )
}
