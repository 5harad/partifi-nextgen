import { Layout } from '../components/Layout'

const CONTACT = 'support@partifi.org'

type FaqItem = {
  question: string
  answer: string
}

const FAQ_ITEMS: FaqItem[] = [
  {
    question: 'Is this service really free?',
    answer: 'Yes! Partifi is completely free and open to everyone.',
  },
  {
    question: 'Can I partifi a landscape score? How do I rotate a score before I partifi it?',
    answer:
      'Partifi doesn\u2019t directly support landscape scores. However, it often works to rotate the score before importing it into Partifi. For example, on a Mac, you can create a portrait version of the landscape score by opening the PDF in Preview, selecting print, ensuring the \u201cauto rotate\u201d option is unselected, and then \u201cSave as PDF\u201d. But in some cases, the lines of music in the rotated score are too small to be usable!',
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
      'Your work on the score is automatically saved every time you make a change. To return to it, just bookmark the URL. Alternatively, the score will be added to your Partifi library automatically if you are logged in to the site.',
  },
  {
    question: 'Is there a way that I can log into Partifi other than through Google?',
    answer:
      'Partifi should all work fine without logging in through Google. You don\u2019t need to log in to use the app and most of the functionality is there even if you don\u2019t log in. The only part of Partifi that you need to login to access, is the Partifi library. If you don\u2019t have a Google account, you need to save the links of your Partifi scores on your personal computer, and access them again that way.',
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
                <p>{item.answer}</p>
              </div>
            ))}

            <p className="faq-contact">
              Still have questions? Contact us at{' '}
              <a className="contact red" href={`mailto:${CONTACT}?subject=Partifi%20FAQ`}>
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
