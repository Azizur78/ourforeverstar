import { Link } from 'react-router-dom'
import Constellation from '../components/Constellation'
import { VerifyLink } from '../components/VerifyModal'
import { CtaBand, Disclaimer, InstagramLink, RecognitionPanel, RelationshipPanel, Section } from '../components/Ui'
import { STEPS } from '../content/steps'
import { useMeta } from '../lib/meta'

const WHY = [
  ['A gift with meaning', 'Not an object that fades into a drawer, but a dedication written for one person and one moment.'],
  ['Beautifully documented', 'Every dedication is recorded in a personal registry, together with its star details and a certificate.'],
  ['Always within reach', 'Open your registry from any phone or computer, at any hour, with your Registry Number and Registry Code.'],
]

export default function Home() {
  useMeta({
    description:
      'Our Forever Star is a celestial keepsake. Dedicate a star to someone who means the world to you, then return to your personal star registry whenever you wish.',
  })

  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">A celestial keepsake</p>
            <h1 className="hero-title">
              Some connections are too <em>extraordinary</em> to be&nbsp;forgotten.
            </h1>
            <p className="lede">
              Dedicate a star to the one who means the world to you. A lasting tribute for everything ordinary gifts
              cannot say, kept in a personal registry you may return to at any time.
            </p>
            <div className="actions">
              <InstagramLink>Dedicate a Star</InstagramLink>
              <VerifyLink className="btn btn-ghost">Verify Your Registry</VerifyLink>
            </div>
          </div>
          <Constellation className="hero-art" />
        </div>
      </section>

      <Section narrow className="center-text" eyebrow="The idea">
        <h2>Give someone a star of their own to be remembered by.</h2>
        <p className="prose">
          For the person you celebrate, remember, or simply cannot stop thinking about. You choose the words; we record
          your dedication, prepare its star details and certificate, and keep everything ready for you to revisit.
        </p>
        <Link to="/celestial-gifting" className="text-link">Discover celestial gifting</Link>
      </Section>

      <Section eyebrow="How it works" title="From a first message to a star you can revisit">
        <ol className="steps-compact">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <span className="step-num" aria-hidden="true">{i + 1}</span>
              <h3>{s.short}</h3>
            </li>
          ))}
        </ol>
        <p><Link to="/how-it-works" className="text-link">See the full journey</Link></p>
      </Section>

      <Section eyebrow="Why Our Forever Star" title="Made to be given, kept and revisited">
        <div className="card-grid three">
          {WHY.map(([t, b]) => (
            <article className="card" key={t}>
              <h3>{t}</h3>
              <p>{b}</p>
            </article>
          ))}
        </div>
      </Section>

      <RecognitionPanel />

      <RelationshipPanel />

      <CtaBand
        title="Already have a star?"
        actions={<VerifyLink className="btn btn-primary">Verify Your Registry</VerifyLink>}
      >
        Enter your Registry Number and Registry Code to view your dedication, your star details and your certificate.
      </CtaBand>

      <div className="container"><Disclaimer /></div>
    </>
  )
}
