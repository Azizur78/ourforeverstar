import { VerifyLink } from '../components/VerifyModal'
import { InstagramLink, PageHero } from '../components/Ui'
import { INSTAGRAM_URL } from '../lib/config'
import { useMeta } from '../lib/meta'

export default function Contact() {
  useMeta({
    title: 'Contact',
    description: 'Contact ourforeverstar on Instagram to dedicate a star, ask a question or get help with your registry.',
  })
  return (
    <>
      <PageHero eyebrow="Contact" title="Let us talk about your star">
        Instagram is how we take orders, answer questions and help with registries.
      </PageHero>
      <section className="section">
        <div className="container narrow">
          <div className="card contact-card">
            <h2>Message us on Instagram</h2>
            <p>
              To dedicate a star, ask about the process, or get help finding your registry details, send us a direct
              message. We will reply as soon as we can.
            </p>
            <div className="actions">
              <InstagramLink>Open Instagram</InstagramLink>
              <VerifyLink className="btn btn-ghost">Verify Registry</VerifyLink>
            </div>
            {!INSTAGRAM_URL && (
              <p className="muted small">The Instagram link has not been configured yet (set INSTAGRAM_URL).</p>
            )}
          </div>
        </div>
      </section>
    </>
  )
}
