# Audit evidence and reproduction

These artifacts describe the unmodified application at the 2026-10-04 audit. They are historical results, not acceptance of future repairs.

| File | Meaning |
|---|---|
| `existing-suite.xml` | Existing tests: 39 passed. |
| `probes.xml` | Independent adversarial checks: 40 total, 37 failed, 3 passed. Failures overlap and include corrected/future integration requirements. |
| `summary.json` | Audit environment, source file hashes/line counts, failure details and feasibility result. |
| `feasibility-output.txt` | Actual feasibility script output; Pulse unavailable yet current gate passes the handmade adapter. |

The independent probe source is `scripts/audit_regressions.py`, outside default `tests/` collection. Read the audit report before interpreting its failures. A01, A24, A32 and A34 have specific interpretation/interface notes in the handoff; preserve observable acceptance intent rather than old internal method names after refactoring.

Application code was not changed. Audit dependencies are isolated in `.audit-deps`; they are not project source and should not be copied into a commit or presentation package. The normal Windows `python` command was an unavailable WindowsApps alias, so these runs used the bundled Python below.

From `C:\Users\hp\Desktop\PDTT`, run in PowerShell:

```powershell
$auditPython = 'C:/Users/hp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'

# Original suite. Exit 0 means the command completed successfully.
& $auditPython -c 'import sys; sys.path.insert(0,".audit-deps"); import pytest; raise SystemExit(pytest.main(["--basetemp=artifacts/audit/recheck-original-tmp", "--junitxml=artifacts/audit/recheck-original.xml"]))'

# Independent acceptance probes. Exit 1 is expected on the audited application.
& $auditPython -c 'import sys; sys.path.insert(0,".audit-deps"); import pytest; raise SystemExit(pytest.main(["scripts/audit_regressions.py", "-o", "addopts=", "-q", "--tb=short", "--basetemp=artifacts/audit/recheck-probe-tmp", "--junitxml=artifacts/audit/recheck-probes.xml"]))'
```

With a repaired normal project environment, the equivalents are:

```powershell
python -m pytest --basetemp=artifacts/audit/recheck-original-tmp --junitxml=artifacts/audit/recheck-original.xml
python -m pytest scripts/audit_regressions.py -o addopts= -q --tb=short --basetemp=artifacts/audit/recheck-probe-tmp --junitxml=artifacts/audit/recheck-probes.xml
```

Use new artifact filenames for repair results so the original audit evidence remains available. Pinned audit versions are recorded in `summary.json`; this was an isolated environment, not a reproduction of every package version used in the Gemini session.
