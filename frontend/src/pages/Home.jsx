import { Link } from 'react-router-dom'
import Constellation from '../components/Constellation'
import { VerifyLink } from '../components/VerifyModal'
import { CtaBand, Disclaimer, InstagramLink, Section } from '../components/Ui'
import { STEPS } from '../content/steps'
import { useMeta } from '../lib/meta'

const WHY = [
  ['A gift with meaning', 'Not an object that fades into a drawer, but a dedication written for one person and one moment.'],
  ['Beautifully documented', 'Every dedication is recorded in a personal registry with its star details and a certificate.'],
  ['Always within reach', 'Verify your registry from any phone or computer, any time, using your Registry Number and Code.'],
]

export default function Home() {
  useMeta({
    description:
      'ourforeverstar is a celestial gifting experience. Dedicate a star to someone who means the world to you, then verify and revisit your registry anytime.',
  })

  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Celestial gifting</p>
            <h1>Some connections are written in the&nbsp;stars.</h1>
            <p className="lede">
              Dedicate a star to someone who means the world to you. A quiet, lasting way to say what ordinary gifts
              cannot, recorded in a registry that is yours to revisit.
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
        <h2>Dedicate a star to someone who means the world to you.</h2>
        <p className="prose">
          For the person you celebrate, remember or simply cannot stop thinking about. Choose the words. We record your
          dedication, prepare your star details and certificate, and keep it all in a registry you can open whenever
          you wish to look up.
        </p>
        <Link to="/celestial-gifting" className="text-link">Explore celestial gifting</Link>
      </Section>

      <Section eyebrow="How it works" title="Five simple steps, one lasting dedication">
        <ol className="steps-compact">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <span className="step-num" aria-hidden="true">{i + 1}</span>
              <h3>{s.title}</h3>
            </li>
          ))}
        </ol>
        <p><Link to="/how-it-works" className="text-link">See the full process</Link></p>
      </Section>

      <Section eyebrow="Why ourforeverstar" title="Made to be given, kept and revisited">
        <div className="card-grid three">
          {WHY.map(([t, b]) => (
            <article className="card" key={t}>
              <h3>{t}</h3>
              <p>{b}</p>
            </article>
          ))}
        </div>
      </Section>

      <CtaBand
        title="Already have a star?"
        actions={<VerifyLink className="btn btn-primary">Verify Your Registry</VerifyLink>}
      >
        Enter your Registry Number and Registry Code to view your dedication, star details and certificate.
      </CtaBand>

      <CtaBand
        title="Ready to dedicate a star?"
        actions={<InstagramLink>Message us on Instagram</InstagramLink>}
      >
        Orders and enquiries happen through Instagram. Tell us who the star is for and we will take care of the rest.
      </CtaBand>

      <div className="container"><Disclaimer /></div>
    </>
  )
}
