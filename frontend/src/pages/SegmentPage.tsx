import { useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'

export function SegmentPage() {
  const { privateId } = useParams<{ privateId: string }>()

  return (
    <Layout>
      <div id="main" style={{ height: '750px', padding: '40px' }}>
        <p className="bold">Segment editor (Phase 3)</p>
        <p>
          Import completed for partset <span className="red">{privateId}</span>. The segment editor will be built
          next.
        </p>
      </div>
    </Layout>
  )
}
