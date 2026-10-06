import { Link } from 'react-router-dom'
import { CtaBand, InstagramLink, PageHero, Section } from '../components/Ui'
import { useMeta } from '../lib/meta'

// NOTE: Editable placeholder copy. Replace with the real brand story when it is ready.
export default function About() {
  useMeta({
    title: 'Our Story',
    description: 'The idea behind ourforeverstar: a quiet, meaningful way to dedicate a star to someone you love.',
  })
  return (
    <>
      <PageHero eyebrow="Our story" title="Because some things are too meaningful for words alone">
        ourforeverstar began with a simple belief: the people who matter most deserve gifts that matter just as much.
      </PageHero>

      <Section narrow>
        <p className="prose">
          We created ourforeverstar to give people a thoughtful way to mark the moments that shape their lives:
          the beginnings, the celebrations, and the goodbyes that stay with us.
        </p>
        <p className="prose">
          Every dedication is handled personally and recorded with care. The result is something you can give, keep
          and return to: a name, a message and a star that belongs to that moment.
        </p>
        <p className="prose">
          We keep things simple and honest. An ourforeverstar dedication is a symbolic gift, and we are always clear
          about what it is.
        </p>
      </Section>

      <Section title="What we care about">
        <div className="card-grid three">
          <article className="card"><h3>Meaning first</h3><p>Every dedication starts with a person and a reason.</p></article>
          <article className="card"><h3>Careful records</h3><p>Your registry is kept accurate, private and available when you want it.</p></article>
          <article className="card"><h3>Honest gifting</h3><p>Beautiful, symbolic, and never overstated.</p></article>
        </div>
      </Section>

      <CtaBand title="Dedicate a star" actions={<>
        <InstagramLink>Message us on Instagram</InstagramLink>
        <Link to="/how-it-works" className="btn btn-ghost">How it works</Link>
      </>}>
        We would love to help you find the right words.
      </CtaBand>
    </>
  )
}
