import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

test.use({ actionTimeout: 10_000 })

async function signIn(
  page: Page,
  role: 'Student' | 'Educator',
  email: string,
  password: string,
) {
  await page.goto('/login')
  await page.getByRole('radio', { name: role, exact: true }).check()
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login$/)
}

async function openHistory(page: Page) {
  await expect(
    page.getByRole('heading', { name: 'Attempt history', exact: true }),
  ).toBeVisible()
}

async function checkSmallScreen(page: Page) {
  await page.setViewportSize({ width: 320, height: 900 })
  expect(
    (await new AxeBuilder({ page }).include('main').analyze()).violations,
  ).toEqual([])
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      ),
    )
    .toBeLessThanOrEqual(0)
}

test('assessor authorises a fresh equivalent form and learner starts separate work', async ({
  page,
  browser,
  request,
}) => {
  test.setTimeout(90_000)
  const seeded = await request.post(
    'http://127.0.0.1:4180/e2e/human-workflows-fixture',
  )
  expect(seeded.ok()).toBeTruthy()
  const fixture = await seeded.json()
  await signIn(
    page,
    'Educator',
    fixture.educator_email,
    fixture.educator_password,
  )
  await page.goto('/assessor/review')
  const reassessment = page.getByRole('region', {
    name: 'Reassessment and outcome rule',
  })
  await reassessment
    .getByLabel('Policy approval reason')
    .fill('Select whole, valid evidence under the approved course rule.')
  await reassessment
    .getByRole('button', { name: 'Publish outcome rule' })
    .click()
  await expect(reassessment).toContainText('Published outcome rule:')
  await reassessment
    .getByRole('combobox', { name: 'Fresh equivalent form' })
    .click()
  await page
    .getByRole('option', { name: 'Fresh interference explanation' })
    .click()
  await reassessment
    .getByLabel('Private reassessment reason')
    .fill('PRIVATE: reviewed the equivalence and current decision.')
  await reassessment
    .getByLabel('Reassessment notice to learner')
    .fill('Try the new observation using the same assessment conditions.')
  await reassessment
    .getByRole('button', { name: 'Authorise reassessment' })
    .click()
  await expect(reassessment).toContainText('Reassessment authorised:')
  await page.reload()
  await expect(reassessment).toContainText('Reassessment authorised:')
  await checkSmallScreen(page)

  const context = await browser.newContext()
  const learner = await context.newPage()
  try {
    await signIn(
      learner,
      'Student',
      fixture.student_email,
      fixture.student_password,
    )
    await learner.goto(`/student/tasks/${fixture.task_id}`)
    await openHistory(learner)
    const outcome = learner.getByRole('region', {
      name: 'Current outcome and reassessment',
    })
    await expect(outcome.getByText('INCOMPLETE', { exact: true })).toBeVisible()
    await expect(outcome).not.toContainText('PRIVATE')
    await outcome.getByRole('link', { name: 'Open fresh reassessment' }).click()
    await expect(learner).toHaveURL(new RegExp(fixture.fresh_task_id))
    await expect(
      learner.getByRole('button', { name: 'Submit activity' }),
    ).toBeVisible()
    await learner
      .getByLabel('Your response', { exact: true })
      .fill(
        'The new observation supports the claim because the predicted relationship is present.',
      )
    const submitted = learner.waitForResponse(
      (response) =>
        response.url().endsWith('/submissions') &&
        response.request().method() === 'POST',
    )
    await learner.getByRole('button', { name: 'Submit activity' }).click()
    const response = await submitted
    expect(response.status()).toBe(201)
    expect((await response.json()).id).not.toBe(fixture.response_id)
    await expect(outcome.getByText('INCOMPLETE', { exact: true })).toBeVisible()
    await learner.reload()
    await expect(outcome.getByText('INCOMPLETE', { exact: true })).toBeVisible()
    await checkSmallScreen(learner)
  } finally {
    await context.close()
  }
})

test('learner reports output and assigned humans retain each response and sample accepted feedback', async ({
  page,
  browser,
  request,
}) => {
  test.setTimeout(120_000)
  const seeded = await request.post(
    'http://127.0.0.1:4180/e2e/human-workflows-fixture',
  )
  expect(seeded.ok()).toBeTruthy()
  const fixture = await seeded.json()
  await signIn(page, 'Student', fixture.student_email, fixture.student_password)
  await page.goto(`/student/tasks/${fixture.task_id}`)
  const tutor = page.getByRole('region', {
    name: 'Work through your reasoning',
  })
  await tutor
    .getByLabel('Your reasoning or question')
    .fill('I think the observation supports the claim.')
  await tutor.getByRole('button', { name: 'Send to tutor' }).click()
  await tutor.getByRole('button', { name: 'Report this reply' }).click()
  await tutor
    .getByLabel('Describe the concern')
    .fill('Please check whether the explanation matches this observation.')
  await tutor.getByRole('button', { name: 'Send reply report' }).click()
  await expect(tutor).toContainText('Your report is saved for human review.')
  await page.reload()
  const notices = page.getByRole('region', { name: 'Report updates' })
  await expect(notices).toContainText('Assessor review · open')

  const context = await browser.newContext()
  const staff = await context.newPage()
  try {
    await signIn(
      staff,
      'Educator',
      fixture.educator_email,
      fixture.educator_password,
    )
    await staff.goto('/escalations')
    await staff
      .getByRole('combobox', { name: 'Course and review queue' })
      .click()
    await staff.getByRole('option').first().click()
    await staff.getByRole('combobox', { name: 'Primary owner' }).click()
    await staff
      .getByRole('option', { name: fixture.owner_name, exact: true })
      .click()
    await staff.getByRole('combobox', { name: 'Backup owner' }).click()
    await staff
      .getByRole('option', { name: fixture.backup_name, exact: true })
      .click()
    await staff
      .getByLabel('Acknowledgement target and staffed hours')
      .fill('Within one staffed day; synthetic test schedule.')
    await staff
      .getByLabel('Resolution target and severity rules')
      .fill('Within two staffed days for normal severity.')
    await staff
      .getByLabel('Configuration reason')
      .fill('Synthetic owners approved for this course.')
    await staff
      .getByRole('button', { name: 'Save queue configuration' })
      .click()
    await expect(staff.getByText('Update queue configuration')).toBeVisible()
    await staff.getByRole('button', { name: 'Inspect retained output' }).click()
    await expect(staff.locator('pre')).toContainText('What do you expect')
    await expect(
      staff.getByText(
        'Needs triage: set response targets under the approved schedule.',
      ),
    ).toBeVisible()
    const triage = staff.getByRole('form', { name: 'Respond to report' })
    await triage
      .getByLabel('Acknowledgement target (local time)')
      .fill('2020-01-01T12:00')
    await triage
      .getByLabel('Resolution target (local time)')
      .fill('2027-01-02T12:00')
    await triage
      .getByLabel('Private action or resolution reason')
      .fill('PRIVATE: established the staffed response targets.')
    await triage
      .getByLabel('Notice to learner')
      .fill('Your report has been triaged for a human response.')
    await triage.getByRole('button', { name: 'Record human response' }).click()
    await expect(
      staff.getByRole('alert').filter({ hasText: 'Acknowledgement overdue.' }),
    ).toBeVisible()
    for (const status of ['acknowledged', 'actioned', 'resolved', 'closed']) {
      const form = staff.getByRole('form', { name: 'Respond to report' })
      await form
        .getByLabel('Acknowledgement target (local time)')
        .fill('2027-01-01T12:00')
      await form
        .getByLabel('Resolution target (local time)')
        .fill('2027-01-02T12:00')
      await form
        .getByLabel('Private action or resolution reason')
        .fill(`PRIVATE: human ${status} this report.`)
      await form
        .getByLabel('Notice to learner')
        .fill(`A human has ${status} your concern.`)
      await form.getByRole('button', { name: 'Record human response' }).click()
      await expect(
        staff.getByRole('heading', { name: `learner report · ${status}` }),
      ).toBeVisible()
    }
    await staff.reload()
    await staff
      .getByRole('combobox', { name: 'Course and review queue' })
      .click()
    await staff.getByRole('option').first().click()
    await expect(
      staff.getByRole('heading', { name: 'learner report · closed' }),
    ).toBeVisible()
    await staff
      .getByRole('combobox', { name: 'Accepted feedback', exact: true })
      .click()
    await staff.getByRole('option').first().click()
    await staff
      .getByLabel('Sampling reason')
      .fill('Check a retained accepted explanation against the source.')
    await staff
      .getByRole('button', { name: 'Queue for human sampling' })
      .click()
    await expect(
      staff.getByRole('heading', { name: 'human sample · open' }),
    ).toBeVisible()
    await checkSmallScreen(staff)
    await notices.getByRole('button', { name: 'Refresh reports' }).click()
    await expect(notices).toContainText('A human has closed your concern.')
    await expect(notices).toContainText(
      'A human has acknowledged your concern.',
    )
    await expect(notices).not.toContainText('PRIVATE')
    await checkSmallScreen(page)
  } finally {
    await context.close()
  }
})

test('gamification opt-out persists while learning remains accessible', async ({
  page,
  request,
}) => {
  const seeded = await request.post(
    'http://127.0.0.1:4180/e2e/human-workflows-fixture',
  )
  expect(seeded.ok()).toBeTruthy()
  const fixture = await seeded.json()
  await signIn(page, 'Student', fixture.student_email, fixture.student_password)
  await page.goto('/student/preferences')
  const preference = page.getByRole('region', {
    name: 'Optional points and achievements',
  })
  await preference.getByRole('checkbox').uncheck()
  await preference
    .getByRole('button', { name: 'Save gamification preference' })
    .click()
  await expect(preference).toContainText(
    'Optional points and achievements are off.',
  )
  await page.reload()
  await expect(preference.getByRole('checkbox')).not.toBeChecked()
  await checkSmallScreen(page)
  await page.goto('/student')
  await expect(
    page.getByRole('heading', { name: 'Achievements', exact: true }),
  ).toHaveCount(0)
  await expect(page.getByText('Optional points', { exact: true })).toHaveCount(
    0,
  )
  await page.goto(`/student/tasks/${fixture.task_id}`)
  await expect(
    page.getByRole('button', { name: 'Submit activity' }),
  ).toBeVisible()
  await page.goto('/student/preferences')
  await preference.getByRole('checkbox').check()
  await preference
    .getByRole('button', { name: 'Save gamification preference' })
    .click()
  await expect(preference).toContainText(
    'Optional points and achievements are enabled.',
  )
  await page.goto('/student')
  await expect(
    page.getByRole('heading', { name: 'Achievements', exact: true }),
  ).toBeVisible()
})
