export const PASSWORD_MIN_LEN = 8

interface RegistrationBody {
  email?: string
  password?: string
}

export function validateRegistration(body: RegistrationBody): string[] {
  const errors: string[] = []
  if (!body.email || !/^\S+@\S+\.\S+$/.test(body.email)) errors.push('invalid email')
  if (!body.password || body.password.length < PASSWORD_MIN_LEN) {
    errors.push(`password must be at least ${PASSWORD_MIN_LEN} characters`)
  }
  return errors
}

export function validatePasswordReset(body: { token?: string; password?: string }): string[] {
  const errors: string[] = []
  if (!body.token) errors.push('missing token')
  if (!body.password || body.password.length < PASSWORD_MIN_LEN) {
    errors.push(`password must be at least ${PASSWORD_MIN_LEN} characters`)
  }
  return errors
}
