import type { ReactNode } from 'react'
import { Layout } from '../components/Layout'

const CONTACT = 'support@partifi.org'
const KOFI_URL = 'https://ko-fi.com/partifi'

type FaqItem = {
  question: string
  answer: ReactNode
}

const FAQ_ITEMS: FaqItem[] = [
  {
    question: 'Is this service really free?',
    answer: (
      <>
        Yes! Partifi is completely free and open for everyone to use. But it&apos;s not free to run
        and maintain. If you&apos;d like to support the project, please consider{' '}
        <a href={KOFI_URL} className="red" target="_blank" rel="noopener noreferrer">
          making a donation
        </a>
        .
      </>
    ),
  },
  {
    question: 'Can I partifi a landscape score?',
    answer:
      'Yes! Partifi supports landscape scores and tries to automatically detect the correct page orientation when you first import a PDF.\n\nBut sometimes a score is landscape in disguise: the PDF is portrait-shaped, but the music is turned sideways on the page. Partifi goes by the page dimensions, so those files import as portrait and won\u2019t look right. If that happens, click on \u201cFix page orientation\u201d in Step 2 (the option is right below the score). Partifi re-analyzes the score in the correct orientation and you should be good to go.',
  },
  {
    question: 'Partifi doesn\u2019t seem to be working correctly. What can I do?',
    answer:
      'Try using Chrome or Firefox on a desktop or laptop computer. This fixes many issues. Partifi is not set up to work on an iPad, but we will keep this improvement in mind for the future.',
  },
  {
    question:
      'How do I save a partially finished score so that I can resume working on it another time?',
    answer:
      'Your work on the score is automatically saved every time you make a change. To return to it, just bookmark the URL. Alternatively, the score will be added to your personal library automatically if you are logged in to the site.',
  },
  {
    question: 'How do I log in to Partifi?',
    answer:
      'You can log in with your Google account. But you don\u2019t need to log in to use most of Partifi \u2014 import, edit, preview, and download parts all work without an account. Logging in is only required for your personal library, which saves your scores so you can return to them later. If you don\u2019t have a Google account, bookmark the link to each score on your computer and use that to open it again.',
  },
  {
    question: 'Does Partifi make scores from parts?',
    answer: 'Partifi just works one way. We only help make parts from scores \u2014 hence the name!',
  },
  {
    question: 'How do I include an entire line of rests? How do I create a full line cues?',
    answer:
      'We aren\u2019t set up to add rests, however, we do have a way to add cues. Label cues with any instrument name followed by a space and the word \u201ccue\u201d. So, for example, when the violin isn\u2019t playing but a trumpet is you would label the trumpet part as: \u201ctrumpet cue\u201d. In Step 3 all the parts and the cue part will be listed. Combine the cue part with the instrumental part(s) you would like the cues to appear in. So you would add the violin part and the trumpet cue part together. The cue parts will be greyed out in the final violin part.',
  },
]

function FaqAnswer({ answer }: { answer: ReactNode }) {
  if (typeof answer === 'string') {
    return answer.split('\n\n').map((paragraph) => <p key={paragraph}>{paragraph}</p>)
  }
  return <p>{answer}</p>
}

export function FaqPage() {
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
        <div id="about-header">Frequently Asked Questions</div>
        <div id="about-panel">
          <div id="about-text">
            {FAQ_ITEMS.map((item, index) => (
              <div key={item.question} className="faq-item">
                <p className="faq-question">
                  {index + 1}. {item.question}
                </p>
                <FaqAnswer answer={item.answer} />
              </div>
            ))}

            <p className="faq-contact">
              Still have questions? Contact us at{' '}
              <a className="contact red" href={`mailto:${CONTACT}?subject=Partifi%20Feedback`}>
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
