import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// WCAG 2.2 AA contrast assertions for the design tokens (plan 006 Step 1;
// design authority docs/learnlens/ui-redesign-decisions.md §4.1).
// Read via cwd (vitest runs from the frontend package root); a ?raw import is
// stubbed to '' by the test CSS pipeline, and import.meta.url is http: under jsdom.

const css = readFileSync(join(process.cwd(), 'src/styles/tokens.css'), 'utf8')

function token(name: string): string {
  const match = css.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`))
  if (!match) throw new Error(`token ${name} not found or not a 6-digit hex in tokens.css`)
  return match[1]
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => {
    const c = Number.parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}

function contrast(foreground: string, background: string): number {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return (light + 0.05) / (dark + 0.05)
}

// Every pairing documented in tokens.css as a text role must clear AA (4.5:1).
const textPairs: Array<[string, string]> = [
  ['--ink', '--surface'],
  ['--ink', '--paper'],
  ['--ink', '--surface-sunken'],
  ['--ink-soft', '--surface'],
  ['--ink-soft', '--paper'],
  ['--ink-soft', '--surface-sunken'],
  // Muted text appears on all three grounds (page eyebrows sit on --paper,
  // metric details on --surface-sunken) - the axe-per-route scan caught the
  // --paper pairing failing at the original value (plan 006 Step 10).
  ['--ink-muted', '--surface'],
  ['--ink-muted', '--paper'],
  ['--ink-muted', '--surface-sunken'],
  ['--accent', '--surface'],
  ['--accent', '--paper'],
  ['--accent', '--accent-wash'],
  ['--affirm', '--surface'],
  ['--affirm', '--affirm-wash'],
  ['--attend', '--surface'],
  ['--attend', '--attend-wash'],
  ['--fault', '--surface'],
  ['--fault', '--fault-wash'],
]

describe('design token contrast (WCAG 2.2 AA)', () => {
  it.each(textPairs)('%s on %s reaches 4.5:1', (fg, bg) => {
    expect(contrast(token(fg), token(bg))).toBeGreaterThanOrEqual(4.5)
  })

  it('white text on --accent (primary button) reaches 4.5:1', () => {
    expect(contrast('#ffffff', token('--accent'))).toBeGreaterThanOrEqual(4.5)
  })

  it('white text on --affirm (solid PASS seal) reaches 4.5:1', () => {
    expect(contrast('#ffffff', token('--affirm'))).toBeGreaterThanOrEqual(4.5)
  })

  it('white text on --fault (danger button) reaches 4.5:1', () => {
    expect(contrast('#ffffff', token('--fault'))).toBeGreaterThanOrEqual(4.5)
  })

  it('hairline --line is perceivable against --surface (non-text, informational only)', () => {
    // Not a WCAG text requirement; guards against the border disappearing entirely.
    expect(contrast(token('--line'), token('--surface'))).toBeGreaterThanOrEqual(1.1)
  })
})
