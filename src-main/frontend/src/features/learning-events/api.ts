export type BrowserLearningEvent =
  | {
      eventType: 'task_view'
      taskId: string
      source?: string
    }
  | {
      eventType: 'draft_save'
      taskId: string
      durationMs?: number
    }

export type LearningEventClientOptions = {
  apiBaseUrl?: string
  fetch?: typeof fetch
  createEventId?: () => string
  getCsrfToken?: () => string | null | undefined
}

export type LearningEventClient = {
  record(event: BrowserLearningEvent): void
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const SOURCE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]*$/

export function createLearningEventClient(
  options: LearningEventClientOptions = {},
): LearningEventClient {
  const fetchImplementation = options.fetch ?? globalThis.fetch.bind(globalThis)
  const createEventId =
    options.createEventId ?? (() => globalThis.crypto.randomUUID())
  const apiBaseUrl = (options.apiBaseUrl ?? import.meta.env.VITE_API_BASE_URL ?? '/api/v1')
    .trim()
    .replace(/\/+$/, '')

  return {
    record(event) {
      const payload = buildPayload(event, createEventId)
      if (payload === null) return

      const headers = new Headers({ 'Content-Type': 'application/json' })
      try {
        const csrfToken = options.getCsrfToken?.()
        if (csrfToken && csrfToken.length <= 4_096) {
          headers.set('X-CSRF-Token', csrfToken)
        }
      } catch {
        return
      }

      // Analytics is deliberately best effort: navigation and draft work must never
      // wait for or fail because of this request.
      void fetchImplementation(`${apiBaseUrl || '/api/v1'}/learning-events`, {
        method: 'POST',
        credentials: 'include',
        keepalive: true,
        headers,
        body: JSON.stringify(payload),
      }).catch(() => undefined)
    },
  }
}

function buildPayload(
  event: BrowserLearningEvent,
  createEventId: () => string,
): Record<string, unknown> | null {
  const taskId = event.taskId.trim()
  if (taskId.length === 0 || taskId.length > 255) return null

  let eventId: string
  try {
    eventId = createEventId()
  } catch {
    return null
  }
  if (!UUID_PATTERN.test(eventId)) return null

  if (event.eventType === 'task_view') {
    const source = event.source?.trim()
    if (
      source !== undefined &&
      (source.length === 0 || source.length > 100 || !SOURCE_PATTERN.test(source))
    ) {
      return null
    }
    return {
      event_id: eventId,
      event_type: 'task_view',
      task_id: taskId,
      metadata: source === undefined ? {} : { source },
    }
  }

  const durationMs = event.durationMs
  if (
    durationMs !== undefined &&
    (!Number.isInteger(durationMs) || durationMs < 0 || durationMs > 86_400_000)
  ) {
    return null
  }
  return {
    event_id: eventId,
    event_type: 'draft_save',
    task_id: taskId,
    metadata: durationMs === undefined ? {} : { duration_ms: durationMs },
  }
}

