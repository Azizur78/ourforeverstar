import { useState } from 'react'

/** Password input with an accessible show/hide control (44px+ touch target). */
export default function PasswordField({ id, label, error, hint, autoComplete, value, onChange, required }) {
  const [shown, setShown] = useState(false)
  const describedBy = [error && `${id}-error`, hint && !error && `${id}-hint`].filter(Boolean).join(' ') || undefined
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="pw-wrap">
        <input id={id} type={shown ? 'text' : 'password'} value={value} onChange={onChange}
          autoComplete={autoComplete} required={required} autoCapitalize="none" autoCorrect="off" spellCheck="false"
          aria-invalid={error ? true : undefined} aria-describedby={describedBy} />
        <button type="button" className="pw-toggle" onClick={() => setShown((s) => !s)}
          aria-label={shown ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`} aria-pressed={shown}>
          {shown ? (
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c5 0 8.5 4.2 9.5 7-.4 1.1-1.2 2.5-2.4 3.7M6.6 6.7C4.6 8.1 3.3 10.3 2.5 12c1 2.8 4.5 7 9.5 7 1.5 0 2.9-.4 4.1-1M9.9 9.9a3 3 0 0 0 4.2 4.2" /></svg>
          ) : (
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M2.5 12C3.5 9.2 7 5 12 5s8.5 4.2 9.5 7c-1 2.8-4.5 7-9.5 7s-8.5-4.2-9.5-7z" /><circle cx="12" cy="12" r="3" /></svg>
          )}
        </button>
      </div>
      {hint && !error && <p className="hint" id={`${id}-hint`}>{hint}</p>}
      {error && <p className="field-error" id={`${id}-error`} role="alert">{error}</p>}
    </div>
  )
}
