// 0 = weak ... 3 = strong. Shown as a meter under the password field.
export function passwordStrength(pwd: string): number {
  let score = 0
  if (pwd.length >= 8) score++
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++
  if (/\d/.test(pwd) && /[^\w]/.test(pwd)) score++
  return score
}
