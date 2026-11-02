import { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import styles from './BottomSheet.module.css'

interface BottomSheetProps {
  open: boolean
  onDismiss: () => void
  children: ReactNode
}

// Mobile action sheet anchored to the bottom of the viewport.
export function BottomSheet({ open, onDismiss, children }: BottomSheetProps) {
  if (!open) return null
  return createPortal(
    <>
      <div className={styles.backdrop} onClick={onDismiss} />
      <section className={styles.sheet}>{children}</section>
    </>,
    document.body,
  )
}
