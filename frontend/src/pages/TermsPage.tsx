import { Layout } from '../components/Layout'

const CONTACT = 'support@partifi.org'

export function TermsPage() {
  return (
    <Layout>
      <div id="main">
        <img
          src="/images/notes_bg.jpg"
          width={1190}
          height={252}
          style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
          alt=""
        />
        <div id="about-header">Terms of Service</div>
        <div id="about-panel">
          <div id="about-text">
            <p className="bold">Partifi Terms of Service</p>

            <p>
              Partifi is offered as-is for personal and educational use. By using this site, you agree to
              these terms.
            </p>

            <p>
              You are responsible for ensuring you have the right to use and share any scores you upload.
              Do not upload material you do not have permission to use. Public library contributions must
              respect applicable copyright law.
            </p>

            <p>
              Partifi LLC provides this tool without warranty. We are not liable for any loss or damage
              arising from your use of the service or from scores you create, download, or share.
            </p>

            <p>
              We may update these terms from time to time. Continued use of Partifi after changes are
              posted constitutes acceptance of the revised terms.
            </p>

            <p>
              Questions about these terms? Contact us at{' '}
              <a className="contact red" href={`mailto:${CONTACT}?subject=Partifi%20Terms`}>
                {CONTACT}
              </a>
              .
            </p>
          </div>
        </div>
      </div>
    </Layout>
  )
}
