import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RegisterForm } from '../RegisterForm'

function fill(password: string) {
  const onSubmit = vi.fn()
  render(<RegisterForm onSubmit={onSubmit} />)
  fireEvent.change(screen.getByPlaceholderText('邮箱'), { target: { value: 'a@b.com' } })
  fireEvent.change(screen.getByPlaceholderText('密码（至少 8 位）'), { target: { value: password } })
  fireEvent.click(screen.getByText('注册'))
  return onSubmit
}

describe('RegisterForm', () => {
  it('rejects a 7-character password', () => {
    expect(fill('abc1234')).not.toHaveBeenCalled()
    expect(screen.getByText('密码长度不能少于 8 位')).toBeTruthy()
  })

  it('accepts an 8-character password', () => {
    expect(fill('abcd1234')).toHaveBeenCalled()
  })
})
