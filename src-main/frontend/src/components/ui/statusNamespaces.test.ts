import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// D3 §5.2: status namespaces must never share one component. ResultSeal is the
// only ui component allowed to accept the formal AssessmentResult type
// (plan 006 Steps 2–3).

const uiDir = join(process.cwd(), 'src/components/ui')

function componentSources(dir: string): Array<{ path: string; source: string }> {
  const out: Array<{ path: string; source: string }> = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) out.push(...componentSources(full))
    else if (full.endsWith('.tsx') && !full.endsWith('.test.tsx'))
      out.push({ path: full, source: readFileSync(full, 'utf8') })
  }
  return out
}

describe('status namespace separation (D3 §5.2)', () => {
  it('only ResultSeal accepts the formal AssessmentResult type', () => {
    const offenders = componentSources(uiDir)
      .filter(({ path }) => !path.includes('ResultSeal'))
      .filter(({ source }) => source.includes('AssessmentResult'))
      .map(({ path }) => path)
    expect(offenders).toEqual([])
  })
})
