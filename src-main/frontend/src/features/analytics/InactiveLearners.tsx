import { useId } from 'react'

import { formatDateTime } from './format'
import type { InactiveLearnerPage } from './types'

type InactiveLearnersProps = {
  page: InactiveLearnerPage | null
  loading: boolean
  error: string | null
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}

export function InactiveLearners({
  page,
  loading,
  error,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: InactiveLearnersProps) {
  const headingId = useId()
  const pageSizeId = useId()
  const pageCount = Math.max(1, Math.ceil((page?.total ?? 0) / (page?.page_size ?? pageSize)))
  const currentPage = page?.page ?? 1

  return (
    <section className="analytics-section" aria-labelledby={headingId}>
      <div className="analytics-section__heading-row">
        <div>
          <h2 id={headingId}>Inactive learners</h2>
          <p>No recorded learning event in the last 14 days, including never-active learners.</p>
        </div>
        <label htmlFor={pageSizeId}>
          Rows per page
          <select
            id={pageSizeId}
            value={pageSize}
            disabled={loading}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
          >
            <option value="25">25</option>
            <option value="50">50</option>
            <option value="100">100</option>
          </select>
        </label>
      </div>

      {loading && <p role="status">Loading inactive learners…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && page && page.items.length === 0 && (
        <p>No inactive learners match these filters.</p>
      )}
      {!loading && !error && page && page.items.length > 0 && (
        <div className="analytics-table-scroll">
          <table>
            <caption>Privacy-safe inactive learner references</caption>
            <thead>
              <tr>
                <th scope="col">Pseudonymous learner</th>
                <th scope="col">Last activity (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((learner) => (
                <tr key={learner.pseudonymous_user_id}>
                  <th scope="row">{learner.pseudonymous_user_id}</th>
                  <td>
                    {learner.last_activity_at ? (
                      <time dateTime={learner.last_activity_at}>
                        {formatDateTime(learner.last_activity_at)}
                      </time>
                    ) : (
                      'Never active'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <nav className="analytics-pagination" aria-label="Inactive learner pages">
        <button
          type="button"
          disabled={loading || currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
        >
          Previous
        </button>
        <span aria-live="polite">
          Page {currentPage} of {pageCount}; {page?.total ?? 0} learners
        </span>
        <button
          type="button"
          disabled={loading || currentPage >= pageCount}
          onClick={() => onPageChange(currentPage + 1)}
        >
          Next
        </button>
      </nav>
    </section>
  )
}
