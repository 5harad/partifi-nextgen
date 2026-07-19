import { Layout } from '../components/Layout'

const CONTACT = 'support@partifi.org'

export function PrivacyPage() {
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
        <div id="about-header">Privacy Policy</div>
        <div id="about-panel">
          <div id="about-text">
            <p className="bold">Partifi Privacy Policy</p>

            <p>
              We respect your privacy. This policy describes what information we collect when you use
              partifi.org and how we use it.
            </p>

            <p className="bold">Information you provide</p>
            <p>
              When you upload a score or create a partset, we store the files and metadata needed to run
              the service (for example, title, composer, and part tags you enter). If you sign in with
              Google, we store your Google account ID and name and use them to identify your account and
              show your personal library.
            </p>

            <p className="bold">Automatically collected information</p>
            <p>
              We use a session cookie to keep you signed in. We may log basic technical information (such
              as IP address, browser type, and request timestamps) for security, debugging, and abuse
              prevention.
            </p>

            <p className="bold">Public library</p>
            <p>
              Partsets you contribute to the public library can be viewed and searched by other users.
              Do not upload material you do not have permission to share publicly.
            </p>

            <p className="bold">How we use information</p>
            <p>
              We use your information to operate Partifi, process your uploads, maintain your personal library,
              improve the service, and respond to support requests. We do not sell your personal
              information.
            </p>

            <p className="bold">Third parties</p>
            <p>
              Google Sign-In is subject to Google&apos;s privacy policy. Files are stored on Amazon S3.
              Hosting and infrastructure providers process data on our behalf to run the site.
            </p>

            <p className="bold">Retention and deletion</p>
            <p>
              We retain uploaded content and account data for as long as needed to provide the service.
              You may contact us to request deletion of your account or specific partsets.
            </p>

            <p className="bold">Changes</p>
            <p>
              We may update this policy from time to time. Continued use of Partifi after changes are
              posted constitutes acceptance of the revised policy.
            </p>

            <p>
              Questions about privacy? Contact us at{' '}
              <a className="contact red" href={`mailto:${CONTACT}?subject=Partifi%20Privacy`}>
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
