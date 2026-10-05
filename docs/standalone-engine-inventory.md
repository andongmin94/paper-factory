# Standalone engine inventory

> Initial transition audit. Implementation cleanup is tracked in [standalone-cleanup-inventory.md](standalone-cleanup-inventory.md); removal/move proposals below describe the original state.

Audit date: 2026-10-05 (Asia/Seoul). Starting revision: `ac22fdd`; Python source version: `0.12.0`. This inventory describes the existing engine and the changes needed when the authentication gate passes. It does not attest that the standalone app, subscription inference, installer, or three final studies have passed.

The gate is a real Electron app using the app's own official ChatGPT sign-in, an actual authorized model response, and connection restoration after app restart. Do not begin full research automation before that gate passes. Existing research evidence, installed plugin evidence, and unrelated sessions must remain untouched.

## Reuse

| Source | Responsibility and retained guarantees |
| --- | --- |
| `src/paper_factory/workflow.py`, `workflow_models.py` | Durable research stages, explicit research IDs, frozen submissions, two bounded background experiment jobs, cancellation, recovery, analysis, export, and validated artifact IDs. There is no model provider or account state in the service. |
| `src/paper_factory/workspace.py` | SQLite records, safe relative paths, unlinked files, strict JSON, atomic/fsynced JSON writes, transaction boundaries, and native nonblocking file leases. |
| `src/paper_factory/project.py` | Original source snapshot, commit identity when Git is available, source inventory, SHA256 verification, source sanitization, read-only copied originals, and clone credentials/hooks disabled. |
| `src/paper_factory/autonomous/models.py` | Plan, code bundle, scientific review, manuscript, and frozen artifact schemas. Generated evidence cannot replace controller-held measurements. |
| `src/paper_factory/autonomous/science.py` | Source context redaction, bounded planning/code/review/writing prompts, paired observation validation, scientific controls, trusted descriptive analysis, standalone recomputation script, computed figures, citations, and evidence-linked manuscript rendering. |
| `src/paper_factory/autonomous/quickjs_runner.py`, `quickjs_worker.mjs` | Frozen JS/TS modules, separate production and experiment guests, controller-held production-call gate, actual measurements, fixture limits, trusted TypeScript parser receipts, runtime/source hashes, owned worker journal, and no host-code execution fallback. |
| `src/paper_factory/autonomous/quickjs_windows.py`, `quickjs_macos.py`, `quickjs_guardian.py` | Windows owned Job Object and macOS liveness guardian, bounded cleanup identity, cancellation, crash cleanup, and recovery receipts. |
| Required low-level portions of `src/paper_factory/autonomous/windows_runtime.py` | Windows Job Object creation/assignment/cleanup used by QuickJS and bounded PDF extraction. Keep these helpers when deleting the unrelated full native runner. |
| `src/paper_factory/autonomous/literature.py` | Bounded Crossref metadata, inspected abstracts, allowlisted public PDFs, extraction subprocess lifecycle, and explicit distinction between metadata and reading. |
| Required DOI/metadata helpers in `src/paper_factory/literature.py` | Used by the autonomous literature collector; extract these shared helpers before removing the old manual study/search path. |
| `src/paper_factory/autonomous/repositories.py` | Bounded public GitHub discovery and structural feasibility signals. Restrict product selection to JS/TS callable studies; its existing language set also contains Python. Feasibility scores are not novelty evidence. |
| `src/paper_factory/author.py` | Validated user-supplied author metadata, precedence rules, ORCID/email/URL checks, and no fabricated author values. |
| `src/paper_factory/conversion.py` | Actual Pandoc/Typst/python-docx conversion, bounded execution, failed/partial output removal, native reopen, and source/output SHA256 receipts. Use bundled executables and the supported Typst path for the standalone product. |
| Required types/helpers in `src/paper_factory/models.py` | `Record`, `Asset`, `Project`, UTC timestamps, and portable IDs are engine dependencies. Separate them before removing unused publication/submission models. |

## Modify or move

| Current path or behavior | Required standalone change |
| --- | --- |
| `WorkflowService(home=None)` and `pf_home()` | Pass an explicit app-owned data directory. Creating the service immediately calls `_recover()`; recovery may stop a retained owned worker. Never point a new app or audit at another session's research directory. |
| `autonomous/runner.py` | QuickJS imports bounded helpers/constants from this module. Move these shared helpers out, then remove `DockerRunner` and the default `research_runner()` selection. The current default picks WindowsRunner on Windows and DockerRunner elsewhere; it is not the standalone runtime. Explicitly provide `QuickJSRunner` for the supported JS/TS scope. |
| `ResearchPlan.runtime`, `CodeBundle.runtime` | Remove Python/Node product paths when the app engine is connected; keep only the declared QuickJS scope. Avoid advertising DOM, ambient Node, networked experiments, or other languages. |
| `skills/paper-factory/assets/quickjs-runtime.zip`, `quickjs-runtime.json` | Move into app runtime resources before deleting the plugin directory. Preserve exact archive/inventory/member hashes, bounded extraction, and upstream license files. |
| `skills/paper-factory/scripts/prepare_runtime.py` | Reuse the bounded safe extraction/verification rules inside the app's own runtime preparation. Remove host-probe and plugin resource-location assumptions. |
| `skills/paper-factory/dependency-manifest.json`, `skills/paper-factory/host-dependencies.json`, `skills/paper-factory/scripts/cloud-dependencies.lock`, `skills/paper-factory/wheelhouse/`, `skills/paper-factory/licenses/` | Retain relevant package pins, wheel source/hash/license information as build inputs; generate a standalone platform runtime inventory. These manifests describe prepared plugin hosts and are not evidence of a bundled application runtime. |
| QuickJS Node lookup | `_runtime()` currently uses `PATH`/`PF_NODE_BIN`. Provide the bundled Node 24 executable; record its version/hash. Its private-host gate does not accept arbitrary Node versions. |
| Python and document dependencies | Bundle an interpreter, controller dependencies, Pandoc, Typst, and required fonts in each platform build. Current optional extras and prepared-host wheels do not constitute an app installer. |
| Git source ingestion | `project.ingest()` invokes the external `git` command. Include a verified source-fetching dependency or replace that path with a bounded public GitHub snapshot implementation while retaining pinned commit/original-byte verification. Users cannot be required to install Git. |
| `workflow.py` instructions and reproduction ZIP README | Replace native host/plugin/Cloud/server-owned delivery language with the app's actual supported runtime and reproduction procedure. Keep the evidence and publication-status boundaries. |
| `WorkflowService._public()` | Retain redaction and bounded public state. Main process may resolve verified artifact IDs for file operations; renderer should receive only the intended public DTOs. |
| `.gitignore` | Narrow `/desktop/` so app source is versioned; ignore app dependencies, builds, local state, private runtime, outputs, and credentials. |
| `pyproject.toml`, `.env.example`, `.github/workflows/` | Remove old CLI/host/submission/Docker settings and unused dependencies as their callers disappear. Replace plugin packaging verification with standalone build/runtime checks. Preserve engine integrity checks. |

## Remove after their replacement is active

Do not keep a second supported product or compatibility fallback. Delete obsolete code and its tests together once replacement resources/helpers are in their final locations.

- `plugin.json`, `skills/paper-factory/SKILL.md`, plugin host instructions, plugin installation and Cloud delivery entrypoints.
- `src/paper_factory/cloud.py` and `skills/paper-factory/scripts/run_workflow.py` after a bounded persistent IPC adapter is connected. The existing adapter's strict JSON/bounds/error redaction are useful implementation references; fixed-artifact import and base64 delivery are not standalone research validation.
- Plugin transport builders/probes: `scripts/build_plugin.py`, `build_skill_transfer.py`, `build_package_transfer.py`, `verify_archive_transfer.py`, `ci_verify_plugin.py`, and corresponding Cloud/host/package transfer tests.
- `scripts/build_autonomous_image.py`, `setup_windows.ps1`, `research-runtime-requirements.txt`, `autonomous/windows_runner.py`, full Windows AppContainer execution, Docker execution, and their unsupported-runtime tests after shared QuickJS/literature helpers are separated.
- `src/paper_factory/cli.py` and its `paperfactory` entrypoint after standalone development/packaging/IPC commands are in place.
- Legacy manual study/experiment/manuscript/integrity paths (`research.py`, `experiments.py`, `evidence.py`, `manuscript.py`, `integrity.py`) after references and shared helper/type dependencies are separated. The new research path is WorkflowService; retaining old result import paths would duplicate behavior.
- Out-of-scope venue, policy, submission, publication, preprint, revision, and OJS portal modules (`venues.py`, `venue_policy.py`, `venue_compiler.py`, `submission_package.py`, `publication.py`, `preprints.py`, `revisions.py`, `revision_submission.py`, `portal.py`, `ojs.py`) and their CLI/tests/docs. Keep relevant prior validation evidence separately.
- Old plugin-facing README/docs and phase/development plans once necessary current engine facts and historical evidence references have been integrated into standalone documentation.

## Preserve as historical evidence

Existing `output/`, `.paper-factory/`, `dist/`, installed plugin metadata, source snapshots, execution receipts, worker journals, failed controls, review records, conversion receipts, ZIPs, hashes, and past validation reports are evidence or generated data. They are not reusable app source and must not be deleted or counted as new standalone results. Older docs can be archived as historical records with their actual product/version/host scope; they must not describe the new product as already verified. No existing research workspace or journal was opened through WorkflowService during this audit.

## State and scientific integrity details

- Every workspace holds `records.sqlite3`; workflow records freeze path/size/SHA256 per artifact. `_verify_artifacts()` also validates the original snapshot and full generated code inventory.
- Dispatch commits the running state and execution attempt before starting the background job. The worker handle is checkpointed through `on_handle`; receipts bind source, protocol, and bundle digests. Observations and failed control evidence are retained before analysis.
- `_recover()` reconciles retained owned handles. A retained successful receipt with observations can finish analysis without rerunning the experiment. Failed controls become terminal even if the crash occurred before the terminal-state checkpoint.
- Cleanup uncertainty blocks new operations. A later cleanup receipt binds confirmation to the original execution SHA256 rather than rewriting the original receipt. QuickJS uses a separate `owned-workers.json` journal and owner lease so a second controller cannot reap a live controller's worker.
- `submit_code()` and `submit_manuscript()` reject a negative/issue-bearing `ScientificReview` before creating the submission artifact. The controller explicitly does not attest reviewer independence. The app must durably preserve every actual generation, fresh-context review, rejection, repair, response identity, and content hash before accepted submissions enter the engine.
- The engine has status and bounded material reads but no public workflow-list API. Add the smallest app-owned listing over existing records when the jobs screen is implemented.
- Export recomputes analysis from raw observations and independently renders evidence-linked manuscript bytes. It reopens PDF/DOCX, checks standalone TeX, verifies conversion receipts, and validates ZIP CRC/member size/hash. It does not render every PDF page to pixels or attest absence of visual overlap/clipping; that required final QA remains separate.
- Source provenance currently records `license_assessment: not_performed`. The final repository selection must separately document actual licenses and redistribution assessment before reproduction bundles are counted as complete.

## Minimal future IPC boundary

After the login gate, run one persistent bundled Python process owned by Electron main. Main owns authentication and model calls; neither Python nor renderer receives OAuth tokens. Use newline-delimited JSON with an explicit request ID, an allowlisted method, schema-validated parameters, bounded input/output, and a matching success/error response. Keep diagnostics on stderr and redact public errors. Do not expose a shell, arbitrary command execution, arbitrary file reads, or arbitrary absolute artifact paths.

The required initial methods map directly to engine responsibilities:

| Method | Parameters and result |
| --- | --- |
| `runtime.status` | No user path; return actual bundled runtime capabilities/readiness. |
| `workflow.create` | Approved public repository URL and research goal; return public workflow DTO. |
| `workflow.list`, `workflow.status` | List public records, or a validated research ID; preserve real stage/status/errors. |
| `workflow.readMaterial` | Research ID, declared area/name, bounded offset/limit; reuse `read_material()`. |
| `workflow.submitPlan` | Research ID and validated plan object. |
| `workflow.collectLiterature` | Research ID; collect actual bounded source evidence. |
| `workflow.submitCode`, `workflow.submitManuscript` | Research ID, validated proposal, and real independently recorded review. |
| `workflow.startExperiment`, `workflow.cancel` | Research ID; use existing owned execution/cancellation behavior. |
| `workflow.export` | Research ID; return validated artifact IDs and byte identity. |
| `artifact.resolve` | Research ID and verified artifact ID; result consumed by main for save/open/folder operations. |
| `shutdown` | Close the owned service and report cleanup uncertainty; preserve receipts/journal on failure. |

Main's orchestration record should distinguish a complete confirmed model response from a cancelled/interrupted/incomplete response. Resume by examining persisted workflow, model records, receipt, journal, and cleanup; do not automatically redispatch a scientific experiment. No future IPC implementation was added during this audit.

## Baseline validation performed

All tests used the existing development `.venv` (Python `3.14.8`) and fresh uniquely named OS temporary directories with pytest cache writes disabled. Existing output/evidence directories and other processes were not used. These are baseline tests, not new final studies or standalone installer validation.

| Validation | Observed result | Scope |
| --- | --- | --- |
| `tests/test_workflow.py`, `test_workspace.py`, `test_autonomous_science.py`, `test_conversion.py` | **273 passed**, 57.46 s | Synthetic controller/observation fixtures; durable state, no favorable rerun, failed-control preservation, strict artifact/JSON checks, trusted analysis, and actual document conversion/reopen tests. No live inference or study-network calls. |
| Selected QuickJS/Windows tests below | **10 passed**, 12.09 s | Actual local bundled WASM guest calls, UTF-8 observations, no ambient host/network access, TypeScript original/compiled hashes, cancellation, live owner protection, and Windows controller-crash worker cleanup/recovery. |

The selected QuickJS tests were `test_smallest_real_guest_calls_original_and_retains_unicode`, `test_guest_has_no_ambient_process_filesystem_or_network`, `test_typescript_source_imports_have_compiler_and_original_hash_receipts`, `test_cancellation_confirms_owned_child_exit`, `test_second_supervisor_never_reaps_a_live_controller_worker`, and `test_windows_controller_crash_closes_job_and_recovery_confirms_exit` (including their parameterizations).

Keep these integrity tests when replacing adapters. Add IPC method/size/path boundaries, actual stage-event consistency, owned app shutdown, incomplete-response restoration, original artifact save/open verification, and packaged runtime smoke checks as each supported feature is implemented. Existing CI covers Linux/Windows Python shards and macOS plugin/private-host verification; it does not prove Electron installation, ChatGPT subscription inference, or macOS standalone end-to-end use.
