# Local vector retrieval and source recovery

Section 8.1 now has a configured, persistent local vector retrieval path. The retrieval API, task generation and feedback factories all use `build_retrieval_service`. No external provider, model download, credentials or additional dependency is needed.

## Selection and score meaning

`RAG_RETRIEVAL_BACKEND=local_vector` is the default. `lexical` selects the previous word-overlap ranking formula through the same approved-source eligibility checks. Changing ranking algorithms cannot admit an unapproved, revoked, retired, foreign-course or unscanned source. The old `LocalCourseRetrievalService` remains available for explicit compatibility/test injection; production factories do not select it.

The local vector model is `local-word-hash-2048-sentences-v1`. It applies Unicode normalization and case folding, removes a small fixed set of instruction/stop words, hashes word frequencies into 2,048 signed SHA-256 buckets, uses logarithmic term frequency, and L2-normalizes each vector. It is an implementation of deterministic text features, not a trained semantic model.

Each preserved passage has a whole-passage vector and sentence/line vectors. Queries use the same segmentation. A passage's relevance is the maximum true cosine between those query and passage vectors, clamped to 0–1. This avoids diluting a relevant sentence within a mixed-topic passage. The result still contains the entire original passage and its exact frozen ID. The existing minimum relevance of **0.45 is unchanged**; no additive score boost or automatic threshold reduction is applied. Zero or negative similarities produce no hit. For example, single-fragment `alpha beta` against `alpha` scores about 0.707; an identical fragment scores 1.

The explicit lexical option retains its separate coverage-based score formula and reports `local-approved-lexical-v1`. Scores are not probabilities, content-approval evidence or a measure of learning quality. Scores from different algorithms should not be compared as calibrated measures.

## Source eligibility and lifecycle

The application database supplies every candidate ID, text, label and scope. Before ranking, both algorithms check:

- Matching course on material, source revision and passage; matching revision module when requested.
- A current `APPROVED` source-review event and a successful scan receipt for that revision's original content hash under the active scan policy.
- No material retirement. General course search additionally requires the current indexed source revision and matching current material hash.
- Explicit task source lists resolve only exact frozen passage IDs, never material aliases. Old approved passages remain available after replacement while the replacement must independently be scanned and reviewed. Revocation, retirement or a new scan policy blocks new retrieval even if vectors are cached.

Ranking occurs after eligibility filtering, so ineligible high-scoring vectors cannot crowd an authorized result out of the candidate set. Retrieval audits retain the model/version, query hash, threshold, scores and exact returned passage IDs. The feedback adapter uses authored prompt and criterion/choice text; learner answers and legacy criteria metadata do not select the grounding passage.

Existing unreviewed uploads must be reviewed through the source-approval interface before new runtime retrieval or grounded generation. Processing an upload does not create that human approval. Historical source and citation reads are unchanged.

## Persistence, backup and recovery

The private cache is `<RAG_UPLOAD_DIR>/.vector-cache.sqlite3`. It stores derived numeric vectors and checksums, not source text or authorization records. Keys bind model version, course, exact revision and passage IDs, original content hash and actual passage/fragment text. API and worker processes can reopen the cache; SQLite serializes writes with a bounded five-second lock wait.

Missing vectors and invalid individual rows rebuild automatically from eligible preserved passages on the next search. Model changes use new keys. Old rows may remain on disk, but cannot create a candidate or override the current source controls. A corrupt or inaccessible database returns controlled `vector_index_unavailable`/503 instead of using unchecked content or silently switching algorithms. Existing feedback callers retain their established controlled failure handling.

The cache is disposable and requires no application migration. The existing learning backup captures authoritative source history, scan/course history, database state and current/historical source files; vectors need not be included. Following a restore, the next authorized search reconstructs missing vectors. To reclaim stale entries or recover a corrupt cache, stop API/workers using this upload directory, remove only its `.vector-cache.sqlite3` cache file, and restart. Preserve source files and the application database. The missing-cache test verifies identical ranking and frozen passage IDs after reconstruction.

## Verification and limits

Final focused verification on 11 September 2026: **25 passed in 34.76 seconds** across `test_local_vector_retrieval.py`, `test_task_generation_api.py`, `test_mvp_learning_loop.py` and `test_task16_retrieval.py`. Ruff checks and formatting pass for the 14 affected Python files. This is scoped verification; full integrated CI remains the coordinator's separate check.

Focused cases cover true cosine/threshold behavior, sentence-to-passage provenance, persistence across service instances, invalid-row rebuild, missing-cache rebuild, corrupt-database failure, scope/approval isolation, revoked/retired/policy/rejected-scan denial, and old-passage retrieval after quarantined replacement. Both configured algorithms exercise the control changes. The MVP fixture uses real DOCX processing, source review, task generation, submission and validated feedback with the original passage citation. Generation API fixtures use explicit synthetic source review. These are synthetic local controls, not institutional approval or scanner-efficacy evidence.

Search is an exact linear scan of eligible passage vectors, with SQLite as a persistent cache rather than an approximate-nearest-neighbor server. Large-corpus/concurrent workload capacity is unmeasured. Word hashing can collide and does not infer synonyms or conceptual equivalence; sentence splitting is punctuation-based. Retrieval quality and threshold calibration still require a representative approved evaluation. Real scanner provisioning/signatures and institutional policy approval, and hosted recovery/TLS/availability evidence, remain separate operator/environment work. No paid calls, downloads, deployments, or real study processing were used for this implementation.
