import { Layout } from '../components/Layout'

const CONTACT = 'support@partifi.org'
const SOURCE_REPO_URL = 'https://github.com/5harad/partifi-nextgen'

export function AboutPage() {
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
        <div id="about-header">About Partifi</div>
        <div id="about-panel">
          <div id="about-text">
            <p className="bold">Partifi is a free and automated tool for creating parts from music scores.</p>

            <p>
              Instrumental parts are often not available for historical music. So if you&apos;re like us,
              you&apos;ve spent countless hours cutting up scores and taping the parts together. Partifi
              dramatically streamlines this process, reducing the time to create parts from hours to minutes.
            </p>

            <p>
              Partifi is made for musicians by musicians. By freely offering this part-making tool, and by
              maintaining a publicly accessible library of user-contributed scores, we seek to support and
              encourage the study and performance of early music.
            </p>

            <p>
              We&apos;re working with the online music library{' '}
              <a href="http://imslp.org/wiki" className="red">
                IMSLP
              </a>{' '}
              so you can partifi scores directly from IMSLP via the home page or the
              &#8220;extract parts&#8221; links on IMSLP score pages.
            </p>

            <p>
              Partifi is{' '}
              <a href={SOURCE_REPO_URL} className="red" rel="noopener noreferrer">
                open source
              </a>
              . Contributions, bug reports, and feedback are welcome on GitHub or by email at{' '}
              <a className="contact red" href={`mailto:${CONTACT}?subject=Partifi%20Feedback`}>
                {CONTACT}
              </a>
              . Please try out Partifi and let us know what you think!
            </p>

            <div id="about-pics">
              <div className="pic-row">
                <div className="about-pic">
                  <img src="/images/kelly.gif" alt="Kelly Savage" />
                  <p>
                    <a className="red" href="http://krsavage.com">
                      Kelly Savage
                    </a>{' '}
                    is a harpsichordist in San Francisco. She no longer cuts up scores.
                  </p>
                </div>

                <div className="about-pic">
                  <img src="/images/sharad.gif" alt="Sharad Goel" />
                  <p>
                    <a className="red" href="http://5harad.com">
                      Sharad Goel
                    </a>{' '}
                    is a computer scientist and aspiring musician.
                  </p>
                </div>

                <div className="about-pic">
                  <img src="/images/dante.gif" alt="Dante Meick" />
                  <p>
                    <a className="red" href="http://removabledante.com">
                      Dante Meick
                    </a>{' '}
                    is a graphic designer, problem solver and creative person living in Brooklyn, New York.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
