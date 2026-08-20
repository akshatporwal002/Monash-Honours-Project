import { useState } from 'react'
import type { FormEvent } from 'react'

import type { UserRole } from '../app/types'
import { Button, Field, Input, RadioGroup, cx } from './ui'
import styles from './LoginScreen.module.css'

function LensMark() {
  return (
    <svg className={styles.lens} width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 3v18" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
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
    <main className={cx('ll-root', styles.page)}>
      <section className={styles.card} aria-labelledby="login-title">
        <div className={styles.brand}>
          <LensMark />
          <span className={styles.wordmark}>LearnLens</span>
        </div>
        <h1 id="login-title" className={styles.title}>
          Sign in to LearnLens
        </h1>
        <p className={styles.intro}>Your role and access are verified by the server every time you sign in.</p>

        <form className={styles.form} onSubmit={submit}>
          <RadioGroup
            legend="Workspace"
            name="role"
            value={role}
            onChange={(value) => setRole(value as UserRole)}
            options={[
              { value: 'student', label: 'Student' },
              { value: 'educator', label: 'Educator' },
              { value: 'admin', label: 'Admin' },
            ]}
            className={styles.roles}
          />
          <Field label="Email address">
            <Input
              type="email"
              name="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </Field>
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
          <Button type="submit" variant="primary" loading={busy}>
            Sign in
          </Button>
          <Button type="button" variant="quiet" disabled={busy} onClick={() => void onLoadDemo(role)}>
            Load demo workspace
          </Button>
        </form>
        <p className={styles.note}>Demo setup is available only in local development.</p>
      </section>
    </main>
  )
}
