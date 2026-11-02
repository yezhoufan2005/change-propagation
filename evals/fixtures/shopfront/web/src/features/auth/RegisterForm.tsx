import { FormEvent, useState } from 'react'
import { t } from '../../i18n'
import { passwordStrength } from './passwordStrength'

const MIN_PASSWORD_LENGTH = 8

export function RegisterForm({ onSubmit }: { onSubmit: (data: { email: string; password: string }) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(t('auth.passwordTooShort'))
      return
    }
    onSubmit({ email, password })
  }

  return (
    <form onSubmit={submit}>
      <input value={email} onChange={e => setEmail(e.target.value)} placeholder={t('auth.email')} />
      <input
        type="password"
        value={password}
        minLength={MIN_PASSWORD_LENGTH}
        onChange={e => setPassword(e.target.value)}
        placeholder={t('auth.passwordHint')}
      />
      <meter min={0} max={3} value={passwordStrength(password)} />
      {error && <p className="form-error">{error}</p>}
      <button type="submit">{t('auth.register')}</button>
    </form>
  )
}
