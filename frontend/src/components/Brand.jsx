import logoImage from '../assets/ourforeverstar-logo.jpg'
import { SITE_NAME } from '../lib/config'

/** The official Our Forever Star seal. One place to change if the asset moves. */
export function BrandSeal({ size = 40, className = '' }) {
  return (
    <img src={logoImage} alt={`${SITE_NAME} seal`} className={`brand-seal ${className}`}
      width={size} height={size} style={{ width: size, height: size }} />
  )
}
