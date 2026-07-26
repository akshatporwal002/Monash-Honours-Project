import { useState } from 'react'
import type { FormEvent } from 'react'
import type { UserRole } from '../app/types'
import { Icon } from './ScreenPrimitives'

const roleContent: Record<UserRole, { title: string; detail: string }> = {
  student: {
    title: 'Learn by doing',
    detail: 'Follow a scaffolded pathway, build circuits and turn feedback into progress.',
  },
  educator: {
    title: 'Teach with clarity',
    detail: 'Create grounded activities and see who needs support while it still matters.',
  },
  admin: {
    title: 'Keep learning reliable',
    detail: 'Manage people, courses and the system settings behind every learning journey.',
  },
}

export function LoginScreen({
  onLogin,
  onLoadDemo,
  busy,
  error,
}: {
  onLogin: (email: string, password: string, selectedRole: UserRole) => Promise<void>
  onLoadDemo: (selectedRole: UserRole) => Promise<void>
  busy: boolean
  error: string
}) {
  const [role, setRole] = useState<UserRole>('student')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void onLogin(email.trim(), password, role)
  }

  return (
    <main className="login-screen">
      <h1 className="sr-only">QuantumLearn</h1>
      <div className="quantum-backdrop" aria-hidden="true">
        <div className="circuit-line circuit-line--one"><i /><i /><i /></div>
        <div className="circuit-line circuit-line--two"><i /><i /></div>
        <div className="circuit-line circuit-line--three"><i /><i /><i /><i /></div>
        <div className="orb orb--one" />
        <div className="orb orb--two" />
      </div>

      <section className="login-story">
        <a className="brand brand--large" href="#login">
          <span className="brand-mark"><i /><i /><b /></span>
          <span>Quantum<strong>Learn</strong></span>
        </a>
        <div>
          <p className="eyebrow">Quantum fluency, one step at a time</p>
          <h1>{roleContent[role].title}</h1>
          <p>{roleContent[role].detail}</p>
        </div>
        <dl className="login-stats" aria-label="Platform statistics">
          <div><dt>Role workspaces</dt><dd>3</dd></div>
          <div><dt>Task formats</dt><dd>6</dd></div>
          <div><dt>Authoring steps</dt><dd>4</dd></div>
        </dl>
      </section>

      <section className="login-card" id="login" aria-labelledby="login-title">
        <div className="login-card__intro">
          <span className="icon-chip"><Icon name="circuit" /></span>
          <p className="eyebrow">Secure learning space</p>
          <h2 id="login-title">Welcome back</h2>
          <p>Choose your workspace and sign in with your QuantumLearn account.</p>
        </div>

        <div className="role-selector" role="group" aria-label="Choose your role">
          {(['student', 'educator', 'admin'] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={role === item ? 'active' : ''}
              aria-pressed={role === item}
              onClick={() => setRole(item)}
            >
              <Icon name={item === 'student' ? 'book' : item === 'educator' ? 'course' : 'settings'} size={18} />
              <span>{item === 'admin' ? 'Admin' : `${item[0].toUpperCase()}${item.slice(1)}`}</span>
            </button>
          ))}
        </div>

        <form className="login-form" onSubmit={submit}>
          <label>
            <span>Email address</span>
            <input
              type="email"
              name="email"
              autoComplete="email"
              placeholder={`${role}@quantumlearn.edu`}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            <span>Password</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button--primary button--wide" disabled={busy}>
            {busy ? 'Signing in…' : `Enter ${role === 'admin' ? 'admin' : role} workspace`}
            {!busy && <Icon name="arrow" size={18} />}
          </button>
          <button
            className="button button--ghost button--wide"
            type="button"
            disabled={busy}
            onClick={() => void onLoadDemo(role)}
          >
            Load demo workspace
          </button>
        </form>
        <p className="login-card__privacy">Demo setup is available only in local development. Your role and access are always verified by the server.</p>
      </section>
    </main>
  )
}
