import { apiUrl } from '../urls'
import { expect, test as base } from '@playwright/test'

type AssessmentReviewFixture = {
  student_email: string
  student_password: string
  task_id: string
  educator_email: string
  educator_password: string
  course_id: string
  attempt_id: string
  response_id: string
  decision_id: string
}

export { expect }

// Playwright runs this test-scoped fixture again for every project and retry.
// The server creates new records on every call, with no shared decision to reset.
export const test = base.extend<{ assessmentReview: AssessmentReviewFixture }>({
  assessmentReview: async ({ request }, provideFixture, testInfo) => {
    const response = await request.post(`${apiUrl}/e2e/assessment-review-fixture`)
    expect(response.ok()).toBeTruthy()
    const fixture: AssessmentReviewFixture = await response.json()
    await testInfo.attach('assessment-records', {
      body: JSON.stringify({
        course_id: fixture.course_id,
        attempt_id: fixture.attempt_id,
        response_id: fixture.response_id,
        decision_id: fixture.decision_id,
        project: testInfo.project.name,
        retry: testInfo.retry,
        repeat: testInfo.repeatEachIndex,
      }),
      contentType: 'application/json',
    })
    await provideFixture(fixture)
  },
})
