import { ReactNode, useState } from 'react'

export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  const [show, setShow] = useState(false)
  return (
    <span className="tooltip-anchor" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && <span className="tooltip-bubble">{text}</span>}
    </span>
  )
}
