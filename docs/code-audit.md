# Precision code audit

Reviewed 2026-10-02 on native Windows. Scope: desktop UI and Electron bridge,
local backend/authentication, autonomous execution and evidence, manuscript
conversion, build scripts and their regression checks. The CLI, standalone
browser workflow and documented Linux runner remain supported paths.

## Removed duplication and obsolete code

- Split the connection card, progress view and paper library into UI components
  with explicit inputs/actions. `App.tsx` decreased from 1,191 to 758 lines.
- Removed the unused artifact-read IPC, bridge method/type, preview size constant
  and renderer alias. Saving/opening paper artifacts uses the existing native
  dialog operations.
- Reused one strict JSON decoder across experiments, model output, runners,
  pipeline evidence, journal responses and standalone reproduction scripts.
- Reused the existing converter for both LaTeX and PDF manuscript compilation.
- Removed the runtime builder's unlocked dependency resolution and lockfile
  generation fallback. Every build requires the checked-in dependency lock.
- Corrected the formatter's nonrecursive directory arguments. App code is now
  checked alongside Electron/shared code and scripts; unchanged upstream UI,
  theme and license sources remain excluded. CI runs this check too.
- Corrected stale setup/version documentation while retaining historical
  research and verification evidence.

## Reproduced defects and corrections

| Defect | Correction |
| --- | --- |
| A failed project detail refresh replaced saved progress with the sparse project list response | Preserve existing details, report the failure until the complete refresh settles, and share concurrent refresh requests |
| Ordinary shutdown replaced completed login/logout results with cancellation metadata | Cancel only outstanding authentication work; keep terminal state and logout retry information |
| Concurrent shutdown or research finishing immediately before cancellation prevented reliable closure | Serialize shutdown; accept confirmed completion; retain the app if cleanup/state cannot be confirmed |
| Resuming manuscript writing reused draft/review filenames and overwrote audit history | Allocate increasing attempt numbers and freeze each preserved draft/review |
| Duplicate JSON keys could change failed controls into passing controls; overflow numbers entered evidence | Reject duplicate keys and all nonfinite values before interpreting or retaining JSON |
| Linux PDF worker cleanup skipped descendants after the leader exited | Reuse owned process-tree cleanup, preserving Windows preassignment handling |
| LaTeX export accepted a manuscript edited during conversion | Use the shared source digest check and remove the invalid output on failure |
| On Windows an unread request body hid the intended HTTP error behind a connection reset | Drain only small, declared bodies within a total deadline before sending errors; reject non-ASCII lengths safely |

## Verification

The current Python collection contains 1,491 cases across 39 test modules:
**1,477 passed, 14 platform skips, no remaining failures or uncovered cases**.
Complete tests run in the same four file shards as CI. The initial HTTP failure
is retained in `desktop/output/0.9.0-audit/qa/python-shard-2.xml`; after fixing it,
all five affected modules passed (115 passed, 2 platform skips). Final coverage
replaces those modules' initial results with the final rerun and compares every
case against the current collection, without counting duplicate executions.
The merged result is retained in
`desktop/output/0.9.0-audit/qa/verification.json`. Skips cover unavailable Windows
symlink privileges, named pipes and optional Linux container specifications.

Desktop checks passed: 66 tests, TypeScript, lint, build, and formatting for all
32 application source/script files. Ruff's F/B checks, Python compilation,
dependency consistency and CLI startup passed too.
The final Windows MSI and portable executable built successfully in
`desktop/output/0.9.0-cleanup`; SHA-256 and unsigned status are recorded in
`desktop/output/0.9.0-cleanup/qa/artifacts.json`.

The bundled runtime passed native Python/Node AppContainer execution and actual
PDF/DOCX export with system Python/Node/Git removed from PATH. The final packaged
ASAR and resources matched 40 backend source files and 9 compiled application
files. Local API/IPC protections, all three views, local Pretendard loading and
normal Electron/backend exit passed, with no residual owned processes. All four
captured screens, including About, matched the previous monochrome screenshots
byte for byte. Evidence is retained in
`desktop/output/0.9.0-cleanup/qa/packaged-smoke/summary.json`.

Account/model operations used synthetic fixtures. Actual login/logout, model
calls, research runs and journal submissions were not performed. Linux cleanup
was checked with process-tree regression fixtures on Windows; this audit did not
run a native Linux environment. Packaged smoke used the exact built ASAR and
resources through the Electron SDK; it did not install the MSI on a fresh PC.

The existing monochrome design, bundled Pretendard and upstream neobrutal UI
sources are retained. No project dependency or compatibility layer was added.
