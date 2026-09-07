import { useId } from 'react'
import type { ApiSchemas } from '../../api/generated'

export function AssessedFeedbackDetails({ feedback }: { feedback: ApiSchemas['AssessedFeedbackView'] }) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId}>Evidence for your criteria</h3>
      <p>This guidance refers to your saved response. Your assessor controls the formal result.</p>
      {feedback.criteria.map((criterion) => (
        <section key={criterion.criterion_version_id} aria-label={criterion.learner_description}>
          <h4>{criterion.learner_description}</h4>
          <p>{criterion.guidance}</p>
          <details>
            <summary>Inspect recorded evidence</summary>
            <ul>
              {criterion.evidence.map((evidence) => (
                <li key={evidence.path}>{evidence.statement}</li>
              ))}
            </ul>
          </details>
        </section>
      ))}
      <h3>Supporting source passages</h3>
      {feedback.source_claims.map((source) => (
        <figure key={source.source_id}>
          <blockquote>{source.support_quote}</blockquote>
          <figcaption>{source.source_label}</figcaption>
        </figure>
      ))}
      {feedback.approved_hints.length > 0 && (
        <section aria-label="Approved conceptual hints">
          <h3>Approved conceptual hints</h3>
          <ul>{feedback.approved_hints.map((hint, index) => <li key={index}>{hint}</li>)}</ul>
        </section>
      )}
      <h3>Reflection</h3>
      <p>{feedback.reflection_prompt}</p>
    </section>
  )
}
