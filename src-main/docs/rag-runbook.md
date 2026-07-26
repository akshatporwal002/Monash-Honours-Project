# QuantumLearn RAG runbook

## Local setup

Install the backend RAG extra, run Alembic to the single head, then configure `RAG_DATA_DIR` outside version control. Source files, Chroma data, and model cache folders are deliberately ignored by Git.

## Processing flow

Upload or register an HTTPS material, then call its process endpoint. SQLite owns material/chunk text and course ownership; Chroma is a disposable candidate index. A process failure leaves a safe status/error message and can be retried with `force=true`.

## Recovering Chroma

If Chroma is missing or corrupted, stop the API, remove only the configured `RAG_CHROMA_DIR`, restart it, and force-process every material with status `indexed`. Never delete SQLite or upload storage during an index rebuild.

## Privacy

Retrieval audits keep only a SHA-256 query hash, returned chunk IDs/scores, purpose, model, and latency. Do not persist raw student answers, retrieval queries, prompts, credentials, or direct identifiers in audit records or logs.

## Evaluation

Maintain educator-approved cases with course ID, query, relevant chunk IDs, irrelevant-course IDs, and no-result expectation. Track Hit@1/3/5, MRR, no-result accuracy, leakage count, and p50/p95 latency. The provisional targets are Hit@5 and no-result accuracy of at least 0.80, zero leakage, and warm p95 retrieval latency at most 500 ms.
