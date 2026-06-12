import { Link } from 'react-router-dom'
import { Layout } from '../components/Layout'

const CONTACT = 'support@partifi.org'

const VIDEOS = [
  { title: 'Step I. Importing the Score', src: 'https://fast.wistia.com/embed/iframe/lb47zbh0cv?controlsVisibleOnLoad=true&endVideoBehavior=reset&version=v1&videoHeight=374&videoWidth=640', height: 374 },
  { title: 'Step II. Labeling the Segments', src: 'https://fast.wistia.com/embed/iframe/kxv41f7lg6?controlsVisibleOnLoad=true&endVideoBehavior=reset&version=v1&videoHeight=372&videoWidth=640', height: 372 },
  { title: 'Step III. Previewing the Parts', src: 'https://fast.wistia.com/embed/iframe/dq5h55u26e?controlsVisibleOnLoad=true&endVideoBehavior=reset&version=v1&videoHeight=373&videoWidth=640', height: 373 },
  { title: 'Step IV. Downloading & Sharing the Parts', src: 'https://fast.wistia.com/embed/iframe/cf2gnfjek2?controlsVisibleOnLoad=true&endVideoBehavior=reset&version=v1&videoHeight=374&videoWidth=640', height: 374 },
]

export function HowToPage() {
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
        <div id="howto-header">How to Partifi</div>
        <div id="howto-panel">
          <div id="howto-text">
            We&apos;ve worked hard to make Partifi intuitive and easy to use. The series of short videos below
            walks you through each of the steps necessary to create parts from a score. If these videos still
            leave you with unanswered questions, see our{' '}
            <Link to="/faq" className="red">
              FAQ
            </Link>{' '}
            or contact us at{' '}
            <a className="contact red" href={`mailto:${CONTACT}?subject=Partifi%20Feedback`}>
              {CONTACT}
            </a>{' '}
            and we would be happy to help.
          </div>

          {VIDEOS.map((video) => (
            <div key={video.title}>
              <div className="vid-title">{video.title}</div>
              <iframe
                className="vid-iframe"
                src={video.src}
                title={video.title}
                allow="fullscreen"
                frameBorder={0}
                scrolling="no"
                width={640}
                height={video.height}
              />
            </div>
          ))}
        </div>
      </div>
    </Layout>
  )
}
