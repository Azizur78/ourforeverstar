import { VerifyLink } from '../components/VerifyModal'
import { CtaBand, InstagramLink, PageHero } from '../components/Ui'
import { STEPS } from '../content/steps'
import { useMeta } from '../lib/meta'

export default function HowItWorks() {
  useMeta({
    title: 'How It Works',
    description: 'From choosing your dedication to verifying your registry: how an ourforeverstar dedication works, step by step.',
  })
  return (
    <>
      <PageHero eyebrow="How it works" title="From a feeling to a star in five steps" />
      <section className="section">
        <div className="container narrow">
          <ol className="steps">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <span className="step-num" aria-hidden="true">{i + 1}</span>
                <div>
                  <h2>{s.title}</h2>
                  <p>{s.body}</p>
                  {i === STEPS.length - 1 && <p><VerifyLink className="text-link">Verify your registry</VerifyLink></p>}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>
      <CtaBand title="Start with a message" actions={<InstagramLink>Dedicate a Star</InstagramLink>}>
        Step one is simply telling us who your star is for.
      </CtaBand>
    </>
  )
}
