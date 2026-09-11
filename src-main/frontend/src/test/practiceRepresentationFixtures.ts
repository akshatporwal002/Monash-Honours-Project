import type { ApiSchemas } from '../api/generated'

const emptyCatalog: ApiSchemas['PracticeRepresentationCatalog'] = {
  revision_id: 'synthetic-task-revision',
  review_event_id: 'synthetic-task-review',
  preference_version: 0,
  on_request: false,
  recommended_id: null,
  selected_id: null,
  selection: 'preference',
  explanation: 'No reviewed practice representations are available for this task.',
  choices: [],
}

// Only match the metadata route; a delivery request must have its own fixture.
export function emptyPracticeCatalogResponse(input: RequestInfo | URL): Response | undefined {
  if (!/\/practice-representations\/tasks\/[^/?]+$/.test(String(input))) return undefined
  return new Response(JSON.stringify(emptyCatalog), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
