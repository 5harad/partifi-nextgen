import { useParams } from 'react-router-dom'
import { Layout } from '../components/Layout'
import { PreviewEditor } from '../components/preview/PreviewEditor'

export function PreviewPage() {
  const { privateId } = useParams<{ privateId: string }>()

  if (!privateId) return null

  return (
    <Layout>
      <PreviewEditor privateId={privateId} />
    </Layout>
  )
}
