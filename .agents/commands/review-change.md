# /review-change

Input: plan, current diff, Test Judge verdict, and verification output.

Run the Code Reviewer and Code Quality Reviewer as separate read-only passes. Keep their findings and verdicts separate. Any changed head invalidates earlier approvals for affected code.

Do not request human PR review through this command.
