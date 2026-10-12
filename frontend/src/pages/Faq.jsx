import { Link } from 'react-router-dom'
import { VerifyLink } from '../components/VerifyModal'
import { CtaBand, InstagramLink, PageHero } from '../components/Ui'
import { useMeta } from '../lib/meta'

const FAQS = [
  ['What is Our Forever Star?',
    'Our Forever Star is a symbolic celestial gift. We record your dedication in the Our Forever Star registry together with details of a star and prepare a certificate. It does not confer legal or physical ownership of a star.'],
  ['How do I dedicate a star?',
    'Message us on Instagram with who the star is for, the occasion and the words you would like included. We will guide you from there.'],
  ['Is a dedication recognised by NASA, the IAU or any government?',
    'No. A dedication is recognised within the Our Forever Star registry only. It is a personal, symbolic keepsake, not an official designation by NASA, the IAU or any government.'],
  ['Why are orders taken on Instagram?',
    'We want to build a relationship with every person who places an order, so each one begins as a personal conversation. Every member of the Our Forever Star family is important to us.'],
  ['How do I access my registry?',
    <>Open the Our Forever Star website, choose <VerifyLink className="text-link">Verify Registry</VerifyLink> and enter your Registry Number and Registry Code. QR codes and NFC cards take you to the main website, from where you verify in the same way.</>],
  ['Where can I find my Registry Number?',
    'Your Registry Number is provided to you with your dedication. It looks like HIP-2026-000401. If you cannot find it, contact us on Instagram.'],
  ['Where can I find my Registry Code?',
    'Your Registry Code is shared with you privately when your registry is prepared. Keep it safe: you need both the Registry Number and the Registry Code to open your registry.'],
  ['What happens if I lose my registry details?',
    <>Send a request through our <Link to="/recover" className="text-link">registry recovery form</Link>. Our team reviews every request personally, and we only share details with an address we can verify. You can also <Link to="/contact" className="text-link">contact us on Instagram</Link>.</>],
  ['Can I verify my registry from the website?',
    'Yes. Verification is done securely on our servers, and only the registry that matches your Registry Number and Registry Code is shown.'],
  ['How do I get my certificate?',
    'Once you verify your registry, the Your Documents section lets you download your Star Dedication Certificate and your Certificate of Celestial Registry as PDFs. If one is not there yet, it has not been uploaded; it will appear as soon as it is ready.'],
  ['Can I transfer my registry?', 'Transfer Certificate functionality is Coming Soon.'],
  ['Is the Wallet available?', 'The Wallet is Coming Soon.'],
]

export default function Faq() {
  useMeta({
    title: 'FAQ',
    description: 'Answers about star dedications with Our Forever Star, finding your Registry Number and Code, verifying your registry and your certificate.',
  })
  return (
    <>
      <PageHero eyebrow="FAQ" title="Questions, answered" />
      <section className="section">
        <div className="container narrow">
          <div className="faq">
            {FAQS.map(([q, a]) => (
              <details key={q}>
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>
      <CtaBand title="Still have a question?" actions={<InstagramLink>Message us on Instagram</InstagramLink>}>
        Our team will be happy to help.
      </CtaBand>
    </>
  )
}
