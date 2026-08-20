import type { UserRole } from '../app/types'

export function homePath(role: UserRole): string {
  if (role === 'educator') return '/educator'
  if (role === 'admin') return '/admin'
  return '/student'
}
