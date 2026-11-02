import { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'ghost'

export function Button({ variant = 'primary', className = '', ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button className={`btn btn-${variant} ${className}`} {...rest} />
}
