import { useState } from 'react'
import { api } from '../../api/client'
import { t } from '../../i18n'

export function ResetPasswordForm({ token, onDone }: { token: string; onDone: () => void }) {
  const [pwd, setPwd] = useState('')
  const [pwd2, setPwd2] = useState('')
  const valid = pwd.length >= 8 && pwd === pwd2

  return (
    <form
      onSubmit={e => {
        e.preventDefault()
        if (valid) api.resetPassword(token, pwd).then(onDone)
      }}
    >
      <input type="password" value={pwd} onChange={e => setPwd(e.target.value)} placeholder={t('auth.passwordHint')} />
      <input type="password" value={pwd2} onChange={e => setPwd2(e.target.value)} placeholder={t('auth.confirmPassword')} />
      <button disabled={!valid}>{t('auth.resetPassword')}</button>
    </form>
  )
}
