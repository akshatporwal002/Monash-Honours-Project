import { apiUrl } from './urls'
import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import { expect, test } from './fixtures/assessment'

async function signIn(page: Page, role: 'Student' | 'Educator', email: string, password: string) {
  await page.goto('/login')
  await page.getByRole('radio', { name: role, exact: true }).check()
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login$/)
}

test('learner conversation and review survive reload and reach a scoped assessor', async ({
  page,
  browser,
  assessmentReview: fixture,
}, testInfo) => {
  test.setTimeout(60_000)
  await signIn(page, 'Student', fixture.student_email, fixture.student_password)
  await page.goto(`/student/tasks/${fixture.task_id}`)
  const tutor = page.getByRole('region', { name: 'Work through your reasoning' })
  await expect(tutor.getByLabel('Your reasoning or question')).toBeVisible()
  await tutor
    .getByLabel('Your reasoning or question')
    .fill('I think the observation supports the claim.')
  await tutor.getByRole('button', { name: 'Send to tutor' }).click()
  await expect(
    tutor.getByText('What do you expect to happen in this task, and what is your reason?'),
  ).toBeVisible()
  await page.reload()
  await expect(tutor.getByText('I think the observation supports the claim.')).toBeVisible()

  const result = page.getByRole('region', { name: 'Assessment result and review' })
  // Opening history keeps the original frozen response next to its result.
  const history = page.getByText('Attempt history', { exact: true })
  if (await history.count()) await history.click()
  const attempt = page.locator('summary').filter({ hasText: /Attempt 1/ })
  if (await attempt.count()) await attempt.click()
  await expect(result).toBeVisible()
  await expect(result).toContainText('Awaiting assessor review')
  await expect(result.getByText('PASS', { exact: true })).toHaveCount(0)
  await result
    .getByLabel('What would you like your assessor to review?')
    .fill('Please explain the evidence relationship.')
  await result.getByRole('button', { name: 'Request assessor review' }).click()
  await expect(result.getByRole('heading', { name: 'Review requested' })).toBeVisible()
  expect((await new AxeBuilder({ page }).include('main').analyze()).violations).toEqual([])

  const assessorContext = await browser.newContext()
  const assessor = await assessorContext.newPage()
  try {
    await signIn(assessor, 'Educator', fixture.educator_email, fixture.educator_password)
    await assessor.goto('/assessor/review')
    const requests = assessor.getByRole('region', { name: 'Learner review requests' })
    await expect(requests.getByText('Please explain the evidence relationship.')).toBeVisible()
    await requests.getByRole('button', { name: 'Open decision and evidence' }).click()
    await assessor.getByRole('button', { name: 'Confirm result', exact: true }).click()
    const dialog = assessor.getByRole('alertdialog')
    await dialog
      .getByLabel('Reason (required)')
      .fill('PRIVATE reason: checked the exact frozen response.')
    await dialog.getByRole('button', { name: 'Confirm result', exact: true }).click()
    await expect(
      assessor.getByRole('status').filter({ hasText: 'Confirm result recorded' }),
    ).toBeVisible()
    await expect(dialog).toHaveCount(0)
    await expect(assessor.getByRole('button', { name: 'Confirm result', exact: true })).toBeFocused()

    // Refresh and open are asynchronous reads; wait for the new revision before
    // entering the resolution, and report a lost field at the field itself.
    const [refreshedRequests] = await Promise.all([
      assessor.waitForResponse((response) =>
        new URL(response.url()).pathname === `/api/v1/assessment/courses/${fixture.course_id}/review-requests`
        && response.request().method() === 'GET',
      ),
      requests.getByRole('button', { name: 'Refresh requests' }).click(),
    ])
    expect(refreshedRequests.status()).toBe(200)
    const [openedDecision] = await Promise.all([
      assessor.waitForResponse((response) =>
        new URL(response.url()).pathname === `/api/v1/assessment/decisions/${fixture.decision_id}/review`
        && response.request().method() === 'GET',
      ),
      requests.getByRole('button', { name: 'Open decision and evidence' }).click(),
    ])
    expect(openedDecision.status()).toBe(200)

    const reason = requests.getByLabel('Internal resolution reason')
    const notice = requests.getByLabel('Response to the learner')
    const learnerNotice = 'Your explanation meets the criterion. Review the saved evidence alongside the criterion.'
    await reason.fill('PRIVATE resolution record.')
    await notice.fill(learnerNotice)
    await expect(reason).toHaveValue('PRIVATE resolution record.')
    await expect(notice).toHaveValue(learnerNotice)
    const resolve = requests.getByRole('button', { name: 'Resolve request' })
    await expect(resolve).toBeEnabled()
    await resolve.click()
    await expect(requests.getByText('No pending requests on this page.')).toBeVisible()
    await result.getByRole('button', { name: 'Refresh result' }).click()
    await expect(result.getByText('PASS', { exact: true })).toBeVisible()
    await expect(result).toContainText('Evidence shown')
    await expect(result).toContainText('Your explanation meets the criterion.')
    await expect(result.getByRole('heading', { name: 'Review resolved' })).toBeVisible()
    await expect(result).not.toContainText('Your review request is saved.')
    await expect(result).not.toContainText('PRIVATE')
    await page.setViewportSize({ width: 320, height: 900 })
    await expect
      .poll(
        () =>
          page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          ),
        {
          message: JSON.stringify(
            await page.evaluate(() =>
              [...document.querySelectorAll('main *')]
                .filter((element) => element.getBoundingClientRect().right > 320)
                .map((element) => ({
                  tag: element.tagName,
                  class: element.className,
                  text: element.textContent?.slice(0, 60),
                }))
                .slice(0, 15),
            ),
          ),
        },
      )
      .toBeLessThanOrEqual(0)
    await testInfo.attach('result-panel', {
      body: await result.screenshot(),
      contentType: 'image/png',
    })
  } finally {
    await assessorContext.close()
  }
})

test('reviewed hints require reasoning and disappear at unaided transfer', async ({
  page,
  request,
}) => {
  const response = await request.post(`${apiUrl}/e2e/tutor-episode-fixture`)
  expect(response.ok()).toBeTruthy()
  const fixture = await response.json()
  await signIn(page, 'Student', fixture.student_email, fixture.student_password)
  await page.goto(`/student/tasks/${fixture.task_id}`)
  const tutor = page.getByRole('region', { name: 'Work through your reasoning' })
  const input = tutor.getByLabel('Your reasoning or question')
  for (const expected of [
    'What do you expect to happen in this task, and what is your reason?',
    'Connect the observed pattern to the claim.',
    'Explain the reasoning behind your current approach before we consider another hint.',
  ]) {
    await input.fill('The pattern supports the explanation because it matches the prediction.')
    await tutor.getByRole('button', { name: 'Send to tutor' }).click()
    await expect(tutor.getByText(expected)).toBeVisible()
  }
  await page
    .getByLabel('Your prediction before results')
    .fill('The observation will match the claim.')
  await page.getByRole('button', { name: 'Record prediction for this input' }).click()
  await expect(
    page.getByText('Original prediction recorded. Each changed circuit needs its own checkpoint.'),
  ).toBeVisible()
  await page
    .getByLabel('Explain the result', { exact: true })
    .fill('The observation matches the prediction and supports the claim.')
  await page.getByRole('button', { name: 'Start unaided fresh application' }).click()
  await expect(tutor).toContainText('Fresh application is unaided.')
  await expect(tutor.getByLabel('Your reasoning or question')).toHaveCount(0)
  await expect(tutor.getByText('Connect the observed pattern to the claim.')).toHaveCount(0)
  await expect(page.getByText('PRIVATE fresh solution')).toHaveCount(0)
  await page.reload()
  await expect(tutor).toContainText('Fresh application is unaided.')
  await expect(page.getByRole('region', { name: 'Approved support' })).toContainText(
    'Accessibility',
  )
})
