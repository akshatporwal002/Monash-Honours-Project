import { expect, test } from '@playwright/test'
import { browserDiagnostics } from './browser-diagnostics'

for (const kind of ['throw', 'rejection', 'caught-network'] as const) {
  test(`browser diagnostics distinguish ${kind}`, async ({ page }, testInfo) => {
    const privateValue = 'synthetic-private-observer-value'
    const diagnostics = await browserDiagnostics(page, [privateValue])
    try {
      await page.goto('/login')
      await expect.poll(() => diagnostics.events.some(event => event.kind === 'window-ready')).toBe(true)
      if (kind === 'throw') {
        await page.evaluate(value => { setTimeout(() => { throw new Error(value) }, 0) }, privateValue)
        // ErrorEvent.message may include an engine-specific "Error:" prefix.
        await expect.poll(() => diagnostics.events.some(event => event.kind === 'window-error' && String(event.message).endsWith('[REDACTED]'))).toBe(true)
        await expect.poll(() => diagnostics.events.some(event => event.kind === 'pageerror')).toBe(true)
      } else if (kind === 'rejection') {
        await page.evaluate(value => { void Promise.reject(new Error(value)) }, privateValue)
        await expect.poll(() => diagnostics.events.some(event => event.kind === 'window-unhandledrejection' && event.message === '[REDACTED]')).toBe(true)
        await expect.poll(() => diagnostics.events.some(event => event.kind === 'pageerror')).toBe(true)
      } else {
        await page.route('**/__browser_diagnostic_network_failure', route => route.abort('failed'))
        await page.evaluate(() => fetch('/__browser_diagnostic_network_failure').catch(() => undefined))
        await expect.poll(() => diagnostics.events.some(event => event.kind === 'requestfailed'
          && event.path === '/__browser_diagnostic_network_failure' && !/cancel/i.test(String(event.errorText)))).toBe(true)
        expect(diagnostics.events.filter(event => event.kind === 'window-error' || event.kind === 'window-unhandledrejection')).toEqual([])
      }
      expect(JSON.stringify(diagnostics.events)).not.toContain(privateValue)
    } finally { await diagnostics.save(testInfo) }
  })
}
