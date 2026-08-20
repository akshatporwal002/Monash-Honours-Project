import { createContext, useContext } from 'react'

export interface ToastOptions {
  tone?: 'default' | 'affirm' | 'fault'
}

export interface ToastContextValue {
  toast: (message: string, options?: ToastOptions) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const value = useContext(ToastContext)
  if (!value) throw new Error('useToast must be used inside ToastProvider')
  return value
}
