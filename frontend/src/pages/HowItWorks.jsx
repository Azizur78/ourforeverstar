import { VerifyLink } from '../components/VerifyModal'
import { PageHero, RelationshipPanel } from '../components/Ui'
import { STEPS } from '../content/steps'
import { useMeta } from '../lib/meta'

export default function HowItWorks() {
  useMeta({
    title: 'How It Works',
    description: 'From choosing your dedication to verifying your registry: how a dedication with Our Forever Star unfolds, step by step.',
  })
  return (
    <>
      <PageHero eyebrow="How it works" title="From a first message to a star you can revisit" />
      <section className="section">
        <div className="container narrow">
          <ol className="steps">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <span className="step-num" aria-hidden="true">{i + 1}</span>
                <div>
                  <h2>{s.title}</h2>
                  <p>{s.body}</p>
                  {i === STEPS.length - 1 && <p><VerifyLink className="text-link">Open your registry</VerifyLink></p>}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>
      <RelationshipPanel />
    </>
  )
}
