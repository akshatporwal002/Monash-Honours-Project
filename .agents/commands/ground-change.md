# /ground-change

Input: requested outcome and optional scope.

1. Read the controlling docs and current worktree.
2. Find the affected frontend, backend, data, contract, test, and CI paths.
3. Trace current behaviour and failure handling.
4. Map requirement IDs to evidence.
5. List missing data, policy conflicts, and unverified claims.

Output: a grounded change record using `.agents/context/change-record-template.md`. Do not edit implementation files.
