/** Where a PDF cannot simply be "downloaded" the way it can on a computer. Best effort: used only to show a helpful hint. */
export function savingHint() {
  if (typeof navigator === 'undefined') return ''
  const ua = navigator.userAgent || ''
  // Instagram, Facebook and similar in-app browsers often block file downloads altogether.
  if (/Instagram|FBAN|FBAV|FB_IAB|Line\/|MicroMessenger/i.test(ua)) {
    return 'You are viewing this inside another app, which can block saving files. Open this page in Safari or Chrome to save your document.'
  }
  // iPadOS reports itself as a Mac, so touch support is the tell.
  const ios = /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  if (ios) return 'On iPhone or iPad: tap View, then the Share icon, then Save to Files.'
  return ''
}
