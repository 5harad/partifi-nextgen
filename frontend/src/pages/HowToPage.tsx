import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Layout } from '../components/Layout'

const CONTACT = 'support@partifi.org'

const VIDEOS = [
  { title: 'Step I. Importing the Score', youtubeId: 'xjlul_YnXDo' },
  { title: 'Step II. Labeling the Segments', youtubeId: 'mroIUb88dt4' },
  { title: 'Step III. Previewing the Parts', youtubeId: 'L1gXaM53iug' },
  { title: 'Step IV. Downloading & Sharing the Parts', youtubeId: 'YNhQjJlMhjk' },
] as const

const YT_IFRAME_API = 'https://www.youtube.com/iframe_api'

declare global {
  interface Window {
    YT?: {
      Player: new (
        elementId: string,
        config: {
          videoId: string
          width?: number | string
          height?: number | string
          host?: string
          playerVars?: Record<string, string | number>
          events?: {
            onStateChange?: (event: { data: number; target: YTPlayer }) => void
          }
        },
      ) => YTPlayer
      PlayerState: { PLAYING: number }
    }
    onYouTubeIframeAPIReady?: () => void
  }
}

type YTPlayer = {
  pauseVideo: () => void
  destroy: () => void
}

function loadYouTubeApi(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve()

  return new Promise((resolve) => {
    const previous = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      previous?.()
      resolve()
    }

    if (!document.querySelector(`script[src="${YT_IFRAME_API}"]`)) {
      const script = document.createElement('script')
      script.src = YT_IFRAME_API
      script.async = true
      document.body.appendChild(script)
    }
  })
}

export function HowToPage() {
  const playersRef = useRef<YTPlayer[]>([])

  useEffect(() => {
    let cancelled = false

    void loadYouTubeApi().then(() => {
      if (cancelled || !window.YT) return

      playersRef.current = VIDEOS.map((video, index) => {
        const player = new window.YT!.Player(`howto-yt-${index}`, {
          videoId: video.youtubeId,
          width: 640,
          height: 360,
          host: 'https://www.youtube-nocookie.com',
          playerVars: {
            rel: 0,
            modestbranding: 1,
            playsinline: 1,
            iv_load_policy: 3,
          },
          events: {
            onStateChange: (event) => {
              if (event.data !== window.YT!.PlayerState.PLAYING) return
              for (const other of playersRef.current) {
                if (other !== event.target) other.pauseVideo()
              }
            },
          },
        })
        return player
      })
    })

    return () => {
      cancelled = true
      for (const player of playersRef.current) {
        try {
          player.destroy()
        } catch {
          // Player may already be gone on unmount.
        }
      }
      playersRef.current = []
    }
  }, [])

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

          {VIDEOS.map((video, index) => (
            <div key={video.youtubeId}>
              <div className="vid-title">{video.title}</div>
              <div className="vid-iframe">
                <div id={`howto-yt-${index}`} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  )
}
