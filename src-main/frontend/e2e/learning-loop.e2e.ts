import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { apiUrl } from './urls'

async function signIn(page: Page, role: 'Student' | 'Educator', email: string, password: string) {
  await page.goto('/login')
  await page.getByRole('radio', { name: role, exact: true }).check()
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login$/)
}

test('quantum episode connects checked feedback, revision, model, activity and human result', async ({ page, browser, request }, testInfo) => {
  test.setTimeout(120_000)
  page.setDefaultTimeout(15_000)
  const created = await request.post(`${apiUrl}/e2e/learning-loop-fixture`)
  expect(created.ok()).toBeTruthy()
  const fixture = await created.json()
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await signIn(page, 'Student', fixture.student_email, fixture.student_password)
  await page.goto(`/student/tasks/${fixture.task_id}`)
  await expect(page.getByRole('heading', { name: 'Learning episode', exact: true })).toBeVisible()
  await expect(page.locator('#task-response')).toHaveCount(1)
  await expect(page.getByText(/X followed by two Hadamard gates/)).toHaveCount(0)
  await expect(page.getByText(/zero is restored|the final state is one/i)).toHaveCount(0)
  const tutor = page.getByRole('region', { name: 'Work through your reasoning' })
  for (let index = 0; index < 2; index++) {
    await tutor.getByLabel('Your reasoning or question').fill('How does the Hadamard gate change the zero state?')
    await tutor.getByRole('button', { name: 'Send to tutor' }).click()
    await expect(tutor.getByRole('list', { name: 'Tutor conversation' })).toContainText(index === 0
      ? 'What do you expect to happen in this task, and what is your reason?'
      : 'Connect the input state to the gate and the measurement basis.')
  }
  await page.getByRole('button', { name: 'Add H gate', exact: true }).click()
  await page.getByLabel('Your prediction before results').fill('Zero and one each have probability one half.')
  await page.getByLabel('Your reasoning', { exact: true }).fill('H creates equal amplitudes from the zero input.')
  await page.getByRole('button', { name: 'Record prediction for this input', exact: true }).click()
  await expect(page.getByText('Prediction and current input saved before results.')).toBeVisible()
  await page.getByRole('button', { name: 'Run 1,024 shots', exact: true }).click()
  await expect(page.getByText('Simulation completed and saved with 1,024 shots.')).toBeVisible()
  await page.getByLabel('Explain the result', { exact: true }).fill('Equal amplitudes give equal measurement probabilities. Sampled counts can differ.')
  await page.getByLabel('Your reflection', { exact: true }).fill('The exact probabilities matched my prediction.')
  await page.getByRole('button', { name: 'Start unaided fresh application' }).click()
  await expect(tutor).toContainText('Fresh application is unaided.')
  await expect(tutor.getByLabel('Your reasoning or question')).toHaveCount(0)
  await expect(page.getByText('PRIVATE:', { exact: false })).toHaveCount(0)
  await expect(page.getByText(/the final state is one|X prepares one/i)).toHaveCount(0)
  await page.getByLabel('Fresh application response', { exact: true }).fill('The fresh circuit ends in state one.')
  await page.getByRole('button', { name: 'Add fresh X gate', exact: true }).click()
  await page.getByRole('button', { name: 'Add fresh H gate', exact: true }).click()
  await page.getByRole('button', { name: 'Add fresh H gate', exact: true }).click()
  await page.getByLabel('Fresh application prediction', { exact: true }).fill('One with probability one.')
  await page.getByLabel('Fresh application reasoning', { exact: true }).fill('X prepares one, then H squared restores that input.')
  await page.getByRole('button', { name: 'Record fresh prediction', exact: true }).click()
  await page.getByRole('button', { name: 'Run fresh circuit', exact: true }).click()
  await expect(page.getByText('Fresh application simulation saved. Results are shown in this workspace.')).toBeVisible()
  await page.getByRole('button', { name: 'Save draft', exact: true }).click()
  await expect(page.getByText('Draft saved.', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Fresh application response', { exact: true })).toHaveValue('The fresh circuit ends in state one.')

  async function submit() {
    const receipt = page.waitForResponse(response => response.url().endsWith(`/tasks/${fixture.task_id}/submissions`) && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Submit activity', exact: true }).click()
    const response = await receipt
    expect(response.status()).toBe(201)
    return response.json()
  }
  const first = await submit()
  await expect(page.getByRole('heading', { name: 'Your feedback', exact: true })).toBeVisible()
  await page.getByRole('button', { name: /reviewed this feedback/ }).click()
  await expect(page.getByText('Feedback review recorded.', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Accept suggestion', exact: true })).toBeEnabled()
  await page.getByLabel('Revise an earlier response').selectOption(first.id)
  await page.getByLabel('Reason for your revision').fill('I used the feedback to distinguish probabilities from sampled counts.')
  await page.getByLabel('Your reflection', { exact: true }).fill('The simulation count varies; the exact probability does not.')
  const revised = await submit()
  expect(revised.id).not.toBe(first.id)
  expect(revised.episode.supported.revision.previous_response_version_id).toBe(first.id)
  await expect(page.getByRole('heading', { name: 'Your feedback', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Accept suggestion', exact: true })).toBeEnabled()
  await expect.poll(async () => {
    const evidence = await request.get(`${apiUrl}/e2e/learning-loop/${revised.id}/evidence`)
    return evidence.ok() ? (await evidence.json()).evidence_types : []
  }).toEqual(expect.arrayContaining(['PREDICTION', 'REASONING', 'EXPLANATION', 'REFLECTION', 'REVISION', 'TRANSFER']))
  await page.getByRole('button', { name: 'Accept suggestion', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Open chosen activity' })).toHaveAttribute('href', `/student/tasks/${fixture.next_task_id}`)
  const resultResponse = await page.request.get(`/api/v1/students/me/responses/${revised.id}/result`)
  const result = await resultResponse.json()
  expect(result.result).toBeNull()
  expect(result.status).toBe('Awaiting assessor review')

  const assessorContext = await browser.newContext()
  const assessor = await assessorContext.newPage()
  try {
    await signIn(assessor, 'Educator', fixture.educator_email, fixture.educator_password)
    await assessor.goto('/assessor/review')
    await assessor.getByRole('button', { name: new RegExp(`Inspect attempt ${result.assessment_attempt_id}`) }).click()
    const decisions = assessor.locator('select[id^="decision-"]')
    await expect(decisions).toHaveCount(3)
    for (let index = 0; index < 3; index++) {
      await decisions.nth(index).selectOption('MET')
      await assessor.locator('textarea[id^="reason-"]').nth(index).fill('The exact saved prediction, circuit and fresh response demonstrate this criterion.')
    }
    const checks = assessor.getByRole('checkbox', { name: /Whole immutable learner response/ })
    for (let index = 0; index < await checks.count(); index++) await checks.nth(index).check()
    await assessor.getByLabel('Formal confirmation reason').fill('Synthetic assessor action checks frozen evidence against the unchanged rule.')
    await assessor.getByRole('button', { name: 'Apply frozen pass rule and confirm result' }).click()
    await expect(assessor.getByText('Formal result PASS confirmed. Your criterion decisions and reasons are saved.')).toBeVisible()
  } finally {
    await assessorContext.close()
  }
  await page.reload()
  await expect(page.getByRole('region', { name: 'Assessment result and review' }).filter({ hasText: 'Confirmed by assessor' }).getByText('PASS', { exact: true })).toBeVisible()
  const reports = page.getByRole('region', { name: 'Report updates' })
  await expect(reports).toContainText('Assessor review')
  await expect(reports).not.toContainText('Technical review')
  // Pending-assessment guidance is withheld when the human review history changes.
  await expect(page.getByRole('heading', { name: 'Feedback unavailable', exact: true })).toBeVisible()
  const access = await new AxeBuilder({ page }).include('main').withTags(['wcag2a', 'wcag2aa']).analyze()
  expect(access.violations).toEqual([])
  const screenshot = testInfo.outputPath('complete-learning-loop.png')
  await page.screenshot({ path: screenshot, fullPage: true })
  await testInfo.attach('complete-learning-loop', { path: screenshot, contentType: 'image/png' })
  await page.getByRole('link', { name: 'Open chosen activity' }).click()
  await expect(page).toHaveURL(new RegExp(`/student/tasks/${fixture.next_task_id}$`))
  expect(errors).toEqual([])
})
