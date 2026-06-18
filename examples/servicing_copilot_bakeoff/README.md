# Servicing Copilot Bake-Off Starter

This is a compact vertical slice for a mortgage-servicing copilot trial.

It demonstrates the pieces that matter for a paid bake-off:

- lender-scoped loan tape import;
- idempotent upsert keyed by `(lender_id, loan_number)`;
- append-only case events for auditability;
- borrower email classification into structured output;
- Postgres-oriented schema boundaries for the production version.

The runnable test version uses in-memory SQLite so reviewers can execute it without provisioning infrastructure. `schema.postgres.sql` shows the Postgres shape for a production build.

## Run

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_servicing_copilot_bakeoff -v
```

## Files

- `servicing_copilot.py`: import, event, and classification logic.
- `schema.postgres.sql`: production-shaped Postgres tables and indexes.
- `sample_loan_tape.csv`: minimal sample input.
- `tests/test_servicing_copilot_bakeoff.py`: behavior checks for idempotency, structured classification, and audit events.

## Intent

This is not a full mortgage servicing product. It is a narrow proof that the trial scope can be implemented as a reliable vertical slice: data in, state transition, structured AI output, and auditable events out.
