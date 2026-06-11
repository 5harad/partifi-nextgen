import { Link } from 'react-router-dom'

const CONTACT_EMAIL = 'support@partifi.org'
const SOURCE_REPO_URL = 'https://github.com/5harad/partifi-nextgen'

export function Footer() {
  const year = new Date().getFullYear()

  return (
    <div id="footer">
      <div id="footer-wrapper">
        <div id="share-box">
          <div>
            <img src="/images/email_icon.gif" style={{ verticalAlign: 'middle' }} alt="" />{' '}
            <div className="share-text">
              <a href="mailto:?subject=Partifi&body=A+free+and+automated+tool+for+creating+parts+from+music+scores:+http://partifi.org">
                share with a friend
              </a>
            </div>
          </div>
        </div>

        <div id="blurb">
          Partifi is made for musicians by musicians. By freely offering this part-making tool and
          maintaining a publicly accessible library of user-contributed scores, we seek to support
          the study and performance of historical music.
          <div id="fine-print">
            &copy; {year} Partifi &nbsp;|&nbsp;{' '}
            <Link id="about-link" to="/about">
              About
            </Link>{' '}
            &nbsp;|&nbsp; <a href={`mailto:${CONTACT_EMAIL}`} className="contact">Contact</a>{' '}
            &nbsp;|&nbsp; <Link to="/privacy">Privacy</Link> &nbsp;|&nbsp; <Link to="/terms">Terms</Link>{' '}
            &nbsp;|&nbsp;{' '}
            <a href={SOURCE_REPO_URL} rel="noopener noreferrer">
              Source
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
