import { Link } from 'react-router-dom'
import { VerifyLink } from '../components/VerifyModal'
import { PageHero } from '../components/Ui'
import { useMeta } from '../lib/meta'

export default function NotFound() {
  useMeta({ title: 'Page not found', noindex: true })
  return (
    <>
      <PageHero eyebrow="404" title="This star is out of view">
        The page you are looking for does not exist.
      </PageHero>
      <div className="container narrow center-text">
        <div className="actions center">
          <Link to="/" className="btn btn-primary">Back to Home</Link>
          <VerifyLink className="btn btn-ghost">Verify Registry</VerifyLink>
        </div>
      </div>
    </>
  )
}
