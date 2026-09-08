import { expect, test } from '@playwright/test'

async function login(page: import('@playwright/test').Page, role: 'Student' | 'Educator') {
  await page.goto('/login')
  await page.getByRole('radio', { name: role, exact: true }).check()
  await page.getByRole('button', { name: 'Load demo workspace' }).click()
  await expect(page).toHaveURL(role === 'Student' ? /\/student$/ : /\/educator$/)
}

const history = {
  evidence: [{ id: 'evidence-1', type: 'REASONING', provenance: 'LEARNER_ACTION', occurred_at: '2026-09-08T00:00:00Z' }],
  snapshots: [],
  corrections: [{ annotation: { annotation_id: 'annotation-1', note: 'The recorded context is incomplete.' }, reviews: [] }],
  entries: [{ entry_type: 'OBSERVATION', reference_id: 'evidence-1', occurred_at: '2026-09-08T00:00:00Z' }],
  next_cursor: null,
}

test('authenticated learner reads history and submits a correction', async ({ page }) => {
  await login(page, 'Student')
  await page.route('**/api/v1/learner-model/me/timeline**', route => route.fulfill({ json: history }))
  await page.route('**/api/v1/learner-model/me/annotations', route => route.fulfill({ status: 201, json: {} }))
  await page.goto('/student/learner-model')
  await page.getByLabel('Course ID').fill('course-e2e')
  await page.getByLabel('Outcome ID').fill('outcome-e2e')
  await page.getByRole('button', { name: 'Load history' }).click()
  await expect(page.getByRole('heading', { name: 'Ordered history' })).toBeVisible()
  await page.getByLabel('Evidence ID').fill('evidence-1')
  await page.getByLabel(/Context/).fill('The explanation needs context.')
  await page.getByRole('button', { name: 'Add context' }).click()
  await expect(page.getByRole('status')).toContainText('Your context was added.')
})

test('authenticated educator retains a stale review draft', async ({ page }) => {
  await login(page, 'Educator')
  await page.route('**/api/v1/learner-model/courses/**/timeline**', route => route.fulfill({ json: history }))
  await page.route('**/api/v1/learner-model/courses/**/reviews**', route => route.fulfill({ status: 409, json: { detail: 'stale' } }))
  await page.goto('/educator/learner-model')
  await page.getByLabel('Course ID').fill('course-e2e')
  await page.getByLabel('Learner ID').fill('1')
  await page.getByLabel('Outcome ID').fill('outcome-e2e')
  await page.getByRole('button', { name: 'Load learner history' }).click()
  await page.getByRole('button', { name: 'Review learner note' }).click()
  await page.getByLabel(/Reason/).fill('Please inspect the full context.')
  await page.getByRole('button', { name: 'Add review' }).click()
  await expect(page.getByRole('status')).toContainText('History was refreshed')
  await expect(page.getByLabel(/Reason/)).toHaveValue('Please inspect the full context.')
})
