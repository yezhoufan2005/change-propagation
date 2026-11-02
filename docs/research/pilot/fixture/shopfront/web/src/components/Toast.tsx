import '../styles/toast.css'

interface ToastProps {
  message: string
  type?: 'info' | 'error'
}

export function Toast({ message, type = 'info' }: ToastProps) {
  return (
    <div className={`toast toast-${type}`} role="status">
      {message}
    </div>
  )
}
