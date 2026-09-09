import { apiUrl } from './urls'
import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('formal submission survives task reload, history, and both dashboards', async ({ page, request }) => {
  const fixture = await request.post(`${apiUrl}/e2e/assessed-read-fixture`)
  expect(fixture.ok()).toBeTruthy()
  const ids = await fixture.json() as {
    student_email: string; password: string; task_id: string
    educator_email: string; educator_password: string
  }
  const login = async (role: string, email: string, password: string) => {
    await page.goto('/login')
    await page.getByRole('radio', { name: role, exact: true }).check()
    await page.getByLabel('Email address').fill(email)
    await page.getByLabel('Password').fill(password)
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  }
  await login('Student', ids.student_email, ids.password)
  await expect(page).toHaveURL(/\/student$/)
  await page.goto(`/student/tasks/${ids.task_id}`)
  await expect(page.getByText('Explain the relationship between evidence and claim.')).toBeVisible()
  await page.getByRole('radio').first().check()
  const submitted = page.waitForResponse((response) => response.url().endsWith('/submissions') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Submit activity' }).click()
  const submission = await submitted
  expect(submission.status()).toBe(201)
  expect(await submission.json()).toMatchObject({ score: null, formal_assessment: { result: null, visibility: 'withheld' } })
  await expect(page.getByRole('heading', { name: 'Assessment response saved' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('region', { name: 'Assessment result and review' })).toContainText('Awaiting assessor review')
  await expect(page.getByText('Assessment response saved', { exact: true })).toBeVisible()
  await page.goto('/student')
  await expect(page.getByRole('heading', { name: 'Quantum foundations' })).toBeVisible()
  await expect(page.getByText(/practice average/)).toHaveCount(0)
  await expect(page.getByText(/null%|NaN/)).toHaveCount(0)
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { name: 'Sign in to LearnLens' })).toBeVisible()
  await login('Educator', ids.educator_email, ids.educator_password)
  await expect(page.getByRole('heading', { name: 'Learning pulse' })).toBeVisible()
  await expect(page.getByText(/Assessment response submitted. Formal result unavailable/)).toBeVisible()
  await expect(page.getByText(/null%|NaN/)).toHaveCount(0)
  await page.getByRole('link', { name: 'Students', exact: true }).click()
  await expect(page.getByText('Read Test Student', { exact: true })).toBeVisible()
  await expect(page.getByText('No practice score')).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
})
