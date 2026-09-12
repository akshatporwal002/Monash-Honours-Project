import { writeFile } from 'node:fs/promises'
import type { Page, Request, TestInfo } from '@playwright/test'

type Observation = Record<string, string | number>

// Diagnostic evidence only: keep pageerror assertions independent of this log.
// Do not infer an unhandled rejection from WebKit's transport console events.
export async function browserDiagnostics(page: Page, privateValues: string[] = []) {
  const events: Observation[] = []
  let phase = 'setup'
  let nextRequest = 0
  const requests = new WeakMap<Request, number>()
  const sanitize = (text: string) => {
    let safe = text.replace(/https?:\/\/[^\s)]+/g, url => {
      try { return new URL(url).pathname } catch { return '[URL omitted]' }
    })
    for (const value of privateValues) if (value) safe = safe.replaceAll(value, '[REDACTED]')
    return safe.slice(0, 2000)
  }
  const record = (event: Observation) => {
    if (events.length < 200) events.push({ sequence: events.length, phase, observedAt: Date.now(),
      ...Object.fromEntries(Object.entries(event).map(([key, value]) => [key, typeof value === 'string' ? sanitize(value) : value])),
    })
  }
  const requestId = (request: Request) => {
    if (!requests.has(request)) requests.set(request, ++nextRequest)
    return requests.get(request)!
  }
  const relevant = (request: Request) => new URL(request.url()).pathname === '/api/v1/learner-preferences/me'
  page.on('request', request => {
    if (relevant(request)) record({ kind: 'preferences-request', requestId: requestId(request), path: new URL(request.url()).pathname })
  })
  page.on('response', response => {
    if (relevant(response.request())) record({ kind: 'preferences-response', requestId: requestId(response.request()), status: response.status() })
  })
  page.on('requestfinished', request => {
    if (relevant(request)) record({ kind: 'preferences-finished', requestId: requestId(request) })
  })
  page.on('requestfailed', request => record({ kind: 'requestfailed', requestId: requestId(request), path: new URL(request.url()).pathname, errorText: request.failure()?.errorText ?? '' }))
  page.on('pageerror', error => record({ kind: 'pageerror', name: error.name, message: error.message, stack: error.stack ?? '' }))
  page.on('console', message => {
    if (message.type() === 'error') record({ kind: 'console-error', message: message.text() })
  })
  await page.exposeFunction('__learnLensBrowserDiagnostic', record)
  await page.addInitScript(() => {
    const generation = `${Date.now()}-${Math.random()}`
    const capture = (details: Record<string, string>) => {
      const binding = Reflect.get(window, '__learnLensBrowserDiagnostic')
      if (typeof binding === 'function') {
        void Promise.resolve(binding({ ...details, generation, path: location.pathname })).catch(() => {})
      }
    }
    window.addEventListener('error', event => {
      if (event instanceof ErrorEvent) capture({ kind: 'window-error', message: event.message,
        stack: event.error instanceof Error ? event.error.stack ?? '' : '' })
    })
    window.addEventListener('unhandledrejection', event => capture({ kind: 'window-unhandledrejection',
      message: event.reason instanceof Error ? event.reason.message : String(event.reason) }))
    window.addEventListener('pagehide', () => capture({ kind: 'window-pagehide' }))
    capture({ kind: 'window-ready' })
  })
  return {
    events,
    phase(value: string) { phase = value },
    async save(testInfo: TestInfo) {
      const path = testInfo.outputPath('browser-diagnostics.json')
      await writeFile(path, JSON.stringify(events, null, 2))
      await testInfo.attach('browser-diagnostics', { path, contentType: 'application/json' })
    },
  }
}
