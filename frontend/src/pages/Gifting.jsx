import { VerifyLink } from '../components/VerifyModal'
import { CtaBand, Disclaimer, InstagramLink, PageHero, Section } from '../components/Ui'
import { useMeta } from '../lib/meta'

const OCCASIONS = ['Anniversary', 'Birthday', 'Wedding', 'Engagement', 'Memorial', 'A special relationship', 'A personal milestone', 'A meaningful gift']

export default function Gifting() {
  useMeta({
    title: 'Celestial Gifting',
    description: 'Learn what an ourforeverstar dedication is, who it is for, and the occasions that make a star dedication a meaningful gift.',
  })
  return (
    <>
      <PageHero eyebrow="Celestial gifting" title="A gift as lasting as the feeling behind it">
        An ourforeverstar dedication is a symbolic gift: a star, a name and a message, kept together in your own registry.
      </PageHero>

      <Section narrow title="What is ourforeverstar?">
        <p className="prose">
          ourforeverstar is a celestial gifting experience. When you dedicate a star, we record your dedication in the
          ourforeverstar registry alongside details of the star, such as its catalogue reference and constellation, and
          prepare a certificate to mark the moment.
        </p>
        <p className="prose">
          It is a symbolic gift. A dedication does not give legal or physical ownership of a star: it is a beautiful,
          personal way to connect someone you love with the night sky.
        </p>
      </Section>

      <Section narrow title="Why dedicate a star?">
        <p className="prose">
          Some feelings do not fit into a card or a bouquet. A star is quiet, constant and always overhead for someone,
          somewhere. Dedicating one says that this person, this memory or this milestone deserves a place in the sky.
        </p>
      </Section>

      <Section title="Who can receive one?">
        <p className="prose">Anyone you want to honour. Popular moments include:</p>
        <ul className="chips">
          {OCCASIONS.map((o) => <li key={o}>{o}</li>)}
        </ul>
      </Section>

      <Section narrow title="What the recipient receives">
        <ul className="check-list">
          <li>A dedication recorded in the ourforeverstar registry, with your own message.</li>
          <li>Star details such as catalogue reference, constellation and distance.</li>
          <li>A certificate of the dedication.</li>
          <li>A Registry Number and Registry Code to <VerifyLink className="text-link">verify and revisit the registry</VerifyLink> at any time.</li>
        </ul>
      </Section>

      <CtaBand title="Begin a dedication" actions={<InstagramLink>Dedicate a Star</InstagramLink>}>
        Message us on Instagram with who the star is for and the words you would like to say.
      </CtaBand>
      <div className="container"><Disclaimer /></div>
    </>
  )
}
