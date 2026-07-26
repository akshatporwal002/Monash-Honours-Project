# QuantumLearn RAG runbook

## Local setup

Install the locked backend dependencies, run Alembic to the single head, then configure
`RAG_UPLOAD_DIR` outside version control. Uploaded source files are deliberately ignored by Git.
The runnable MVP does not download an embedding model or require a separate vector service.

## Processing flow

Canonical PDF, DOCX, and PPTX uploads are extracted and chunked immediately. SQLite owns the
material, chunk text, indexing state, and course ownership. The course-scoped lexical retriever
ranks those authorised chunks and emits source labels. A processing failure leaves a safe
status/error message and can be retried through the explicit process endpoint with `force=true`.

## Rebuilding an index

Keep the uploaded files and SQLite database. Force-process the affected saved materials; their
chunks are rebuilt transactionally from the stored source. Never delete SQLite or upload storage
during an index rebuild.

## Privacy

Retrieval audits keep only a SHA-256 query hash, returned chunk IDs/scores, purpose, model, and latency. Do not persist raw student answers, retrieval queries, prompts, credentials, or direct identifiers in audit records or logs.

## Evaluation

Maintain educator-approved cases with course ID, query, relevant chunk IDs, irrelevant-course IDs, and no-result expectation. Track Hit@1/3/5, MRR, no-result accuracy, leakage count, and p50/p95 latency. The provisional targets are Hit@5 and no-result accuracy of at least 0.80, zero leakage, and warm p95 retrieval latency at most 500 ms.
