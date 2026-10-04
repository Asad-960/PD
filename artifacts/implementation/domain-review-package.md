# Fresh review: R2 observer domain boundary

Read `docs/superpowers/plans/2026-10-04-domain-contract-repair.md`,
`artifacts/implementation/domain-contract-progress.md` (including rulings),
`docs/gemini-handoff-2026-10-04.md` R2, and the existing design spec.

Review only the current tranche: `backend/schemas/domain.py`,
`backend/schemas/immutable.py`, constructor/capture/initialize changes in
`simulation/worker.py`, `tests/test_domain_contracts.py`, changed evidence test
fixtures and A37 competing-record construction in `scripts/audit_regressions.py`.
Historical source baseline is in `artifacts/audit/pre-repair-source.zip`; previous
engine repair is recorded separately. No Git repository exists.

Review focus (plan verbatim):
Inspect nested mutability, serialization and validation bypasses, invalid numeric
and metadata types, schedule bounds, adapter compatibility, missingness, and
whether the existing tests still exercise the same acceptance behavior.

Scope: canonical profile hashing and atomic persistence are the next tranche;
worker lifecycle/idempotency and full recovery contracts later; evidence fixes
later. Do not label those unchanged known issues as new defects. Verify current
interfaces are safe for a later read-only council, not clinically valid. No
council, API or UI exists yet. Normal tests currently 156/156.

Report concrete defects with file/line, reproduction, impact and severity.
Document any declined judgments. Do not edit source or historical test outputs.
If you execute independent checks, use a new artifact/basetemp prefix.
Python: C:/Users/hp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe
Dependencies: insert workspace `.audit-deps` into sys.path before pytest/imports.
