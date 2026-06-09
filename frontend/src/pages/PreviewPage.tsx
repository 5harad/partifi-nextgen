import { useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'

export function PreviewPage() {
  const { privateId } = useParams<{ privateId: string }>()

  return (
    <Layout>
      <div id="main" style={{ height: '750px', padding: '40px' }}>
        <p className="bold">Preview editor (Phase 4)</p>
        <p>
          Segment labeling completed for partset <span className="red">{privateId}</span>. The preview editor will be
          built next.
        </p>
      </div>
    </Layout>
  )
}
