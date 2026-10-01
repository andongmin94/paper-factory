# Implementation status

Current workspace: version 0.8.0 with native Windows automatic research.
The Windows work below was verified on 2026-10-01 (Asia/Seoul); older release
evidence is preserved separately.

## Code cleanup and diagnosis

The follow-up audit removed duplicated Python execution drivers, CLI connection
handling, artifact digest/JSON helpers and rollback logic. Unused connection
state, pipeline parameters, local variables, executable OJS version constants,
frontend payload/readiness fallbacks and four unused CSS rule groups were
removed. The duplicate descriptive-table CSV export was also removed; the
canonical `tables.csv` remains. Existing workspace and runtime primitives are
reused without adding project dependencies or a new abstraction layer.

The audit reproduced and corrected deletion of a committed revision manuscript
when its database acknowledgement failed. Model reader/writer thread startup
failures now enter the same owned-process cleanup path as other execution
failures, and connection probes retain uncertain worker ownership. Statistical
analysis rejects nonfinite intermediate values or results caused by overflow of
otherwise finite inputs. Reproducibility exports reject linked directory ancestors, and
Windows observations are decoded strictly as UTF-8, validated and exported from
the same read. Downloads stop at the opened file's declared response length.
Both execution backends reject output directories inside their source/bundle
before creating directories, preserving the input tree on invalid configuration.
Real corrupt/locked SQLite regressions confirm that rollback preserves evidence
and the original operation error when the durable store cannot be checked.
The original Windows login Job handle is also released after an already-exited
leader; failed termination retains the handle and persisted ownership capability.

Frontend readiness now follows the actual subscription provider status, including
an existing CLI login, and clears stale connection information after failed
refreshes. Default web paths use the native `PF_HOME` studies/web directories.

The current Windows collection contains **1,236 cases: 1,222 passed, 14 skipped,
0 failed and 0 uncovered**. Complete fresh file shards and final affected reruns
were deduplicated against the exact current collection. Per-case evidence is
preserved at
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-code-cleanup-verification/result.json`.

The initial broad run exposed an obsolete Docker fixture substring assertion;
the corrected test checks actual mounts and environment bindings. One fake CLI
login preparation also stopped with unconfirmed cleanup. Both affected variants
passed on a focused repeat, and the final full connection report passed 37 cases
with one privilege skip. That initial occurrence's direct cause remains
unconfirmed after pytest removed its temporary metadata. The independently
reproduced Job handle leak above has two real-worker regression cases. No timeout
or cleanup confirmation check was relaxed.

Ruff's Python error and bug checks (`F,B`), dependency validation, source
compilation, JavaScript syntax and patch whitespace checks pass. Audit tools were
installed only in a temporary external directory. A fresh actual ChatGPT
subscription request also completed with confirmed model dispatch and worker
cleanup; its safe summary is preserved at
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-code-cleanup-model-tbig9yu1/safe-summary.json`.
The live-model check is a bounded request; the full native pipeline integration
evidence below still uses explicit synthetic model/literature inputs.

## Native Windows verification

Windows automatic research selects AppContainer and a bounded Job Object.
Docker, WSL and a Linux research image are unnecessary. The setup helper installs
the existing vetted dependency pins and a private official Codex CLI; the start
helper resolves the real Pandoc executable even in a Korean repository path.
`auto doctor` reports ready for the local Python 3.12.14, Node 26.3.0 and official
Codex 0.159.3 installation.

The Windows implementation verification collection contains **1,199 cases: 1,185 passed, 14 skipped,
0 failed and 0 uncovered**. Complete file shards and affected reruns were
deduplicated against the current collection. Two skips target the Linux Docker
controller, one requires a POSIX FIFO, and eleven require unavailable Windows
symlink privileges. Real Windows junction rejection is covered independently.
The exact per-case result is preserved at
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-windows-verification/result.json`.
Dependency validation, source compilation, JavaScript syntax, PowerShell parsing
and patch whitespace checks also pass. GitHub CI was configured for both
Windows and Ubuntu; a new remote CI run was not dispatched during this work.

Actual Python and Node generated-worker tests recorded production calls. Python
could not read the private fixture file, mutate source, connect to loopback or
inherit the controller's secret environment value. Cancellation removed a real
descendant, and recovery restored the staging ACL before cleanup. A separate
native Job Object test terminated a CPU-bound parser at its CPU deadline.
Windows disk limits are monitored directory bounds rather than filesystem
quotas; standard OS resources remain governed by Windows ACLs. Receipts record
these platform details without claiming a read-only host filesystem.

The complete native pipeline used explicitly synthetic model and literature
inputs. Its source execution, seven production calls, twelve paired raw
measurements, trusted analysis, PDF/DOCX/TeX exports, reproducibility ZIP and
independent reanalysis were real. The corresponding runtime/pipeline/science
regression report contains 149 passing cases and no skips:
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-native-runtime-regression.xml`.
This is integration evidence, not a live model-generated autonomous paper.

A separate actual structured model request returned `ready: true`, and the
application probe reported `verified: true`, using the supplied ChatGPT login.
The final repeat after worker ownership fixes completed with
`cleanup_confirmed: true`; its bounded record is preserved at
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-windows-final-model-probe-7zl7jezw/call`.
No credentials were copied into experiments, and no journal submission occurred.

The follow-up subscription audit closed an authentication-change gap after the
assessment checkpoint. Every model call now rejects API-key authentication and
sets the official CLI's `forced_login_method="chatgpt"`, including resumed runs.
The affected provider/connection/pipeline reports contain 151 passes and six
platform/privilege skips; autonomous web checks add 18 passes and one skip.
A fresh actual request after this change completed with ChatGPT authentication,
`ready: true`, confirmed model dispatch and confirmed cleanup. Its safe summary
is preserved at
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-subscription-final-0_nhu219/safe-summary.json`.

Actual staged Mido 1.3.3, Pydantic 2.13.5 and HTTPX 0.28.1 operations also
succeeded inside AppContainer: a MIDI roundtrip, valid/invalid input validation
and construction of an HTTP request without network access. The production
function was called once; the worker and temporary tree were removed. This
exposed and verified the correction for transient staged SSL DLL deletion locks.
The receipt and observations are preserved under
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-windows-dependencies-471_xdko/verified`.

Production Chrome checks used `scripts/start_windows.ps1` from the Korean path.
Local import, inventory experiment, template manuscript, PDF regeneration,
download and integrity review succeeded. The downloaded PDF had four readable
pages. Unsaved title/body edits survived automatic refresh and screen changes;
the page produced no CSP violations. The temporary server and QA tab were closed.

The audit also corrected approval rollback after database commit, readonly
artifact cleanup, unsupported claims in metric units, Windows authentication
locks/ACLs, junction rejection, bounded Windows literature PDF parsing, generated
attempt recovery, execution cleanup accounting, oversized-file listings,
reproducibility ZIP downloads and frontend draft/CSP handling.
Login/model workers now start suspended, join their owned job and resume only
after thread ownership is verified. Constructor, callback and artifact failures
retain uncertain capabilities; unresolved cleanup blocks new/restarted workers.
The final native cleanup/pipeline/dependency regression report contains 44
passing cases with no skips, and the ownership/initialization reports cover 143
distinct cases with 137 passes and six platform/privilege skips.

## Historical version 0.5.0 release evidence

Verified 2026-09-30 (Asia/Seoul). Version 0.5.0. The audited research and venue
path includes evidence-linked revision, separately approved child manuscripts,
immutable same-journal resubmission bundles, rejected-feedback retargeting and
explicit OJS 3.5 initial draft/upload/final-submit/reconciliation commands.
No actual journal submission was performed during development. An authenticated
acceptance run against the user's actual journal and review-round-aware revision
uploads remain target-specific work. See [whole-project audit](project-audit.md)
and [official OJS protocol research](submission-reuse.md).

## Version 0.5.0 verification

The final Windows / Python 3.12.14 collection contains **701 cases**. Complete
file shards, the two portal suites and final affected-case reruns cover that exact
collection: **699 passed, 2 skipped, 0 failed**. The two skips require Windows
symlink creation privileges; ordinary path and junction rejection are exercised
independently. Four initial failures were stale test helpers/fixtures: their
corrections preserve the stricter production conversion and artifact checks.
No passing count includes an unexecuted case. The deduplicated JUnit evidence was
compared with the final `pytest --collect-only` identifiers and preserved at
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-v050-local-verification.json`.

Final portal suites passed 20 and 26 tests. The affected follow-up run passed 114
tests, including all 73 OJS contract cases, all 37 literature cases and the four
corrected fixtures. Dependency validation and source compilation pass. Editable
package metadata and the source both report version 0.5.0.

The first clean GitHub Actions run at code commit
`0831b35fd038c391dcf276124ee06616bb5d9466` also completed successfully:
**all eight Windows/Ubuntu jobs passed**, with every test file assigned to one
of four shards per OS and actual Pandoc/Typst/document libraries installed.
See the [successful full platform run](https://github.com/andongmin94/paper-factory/actions/runs/36706128635).
The public run/job status evidence is preserved at
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-v050-github-verification.json`.

The actual CLI portal smoke completed two independent local research workspaces:
normal delivery and a lost final-provider response. Each genuinely executed the
459-byte corpus experiment, measured 215 compressed bytes (ratio
0.4684095860566449), froze the evidence and generated a real two-page blinded PDF.
The synthetic provider accepted exactly the recorded PDF bytes. Normal delivery
was confirmed by a separate read. Lost-response delivery kept the occupied slot,
blocked cancellation/retry and reconciled by reading the provider, with exactly
one final Submit request. Scientific freezes and ZIPs remained unchanged. All
four PDF pages from the preceding equivalent smoke were rendered and visually
checked for layout, numbering, glyphs and identity leakage.

Latest result: `C:/Users/Public/Documents/ESTsoft/CreatorTemp/
paperfactory-portal-smoke-2iyi0yti/SYNTHETIC-portal-smoke-result.json`.
Providers, policies, authors and receipts are conspicuously synthetic; experiments
and exports are real. The result explicitly records
`external_submission_performed: false`; no real journal request or upload occurred.

The preserved Phase 1 workspace still reports its two successful runs. The Phase
2 ready ZIP validates historically, while its deliberately incomplete genuine
PLOS candidate remains blocked. Phase 3 withdrawal/rejection journals, Phase 4
revision packages and resubmission receipts all validate without modifying their
scientific freezes or histories. Installed 0.5.0 CLI checks also pass the preserved
Phase 2 ready package and both latest portal journals with no errors. The older
phase-specific results below remain historical release evidence.

## Working implementation

Commands: `--help`, `start`, `status`, `research`, `experiment plan/register/run`,
`literature search/doi`, `manuscript build/render/approve`, `integrity check`,
`record-ai-use`, `venue discover/show/select`, `venue policy init/schema/verify/show`,
`submission settings/compile/package/check`,
`submission attestation/attestation-schema/attest/receipt-schema/record-receipt/cancel-attestation/history`,
`preprint settings/schema/prepare/record/check`,
`revision schema/import/draft/plan/apply/experiment/check/response/response-check`,
`revision submission prepare/attestation/attest/record/check`.
Also: `submission portal schema/settings/prepare/upload/inspect/submit/reconcile/check`.

| Component | Responsibility |
| --- | --- |
| models/workspace | Validated identities/states, SQLite, guarded paths, scoped OS locks and atomic artifacts |
| project/research | Sanitized local/Git input, source version, candidate feasibility and explicit studies |
| experiments/evidence | Real isolated-copy subprocesses, failure records, raw-to-claim numerical verification |
| literature/author | Audited Crossref metadata and explicit/environment author identity |
| manuscript/integrity | Editable canonical prose, scientific approval and independent immutable freeze |
| venues/venue_policy | Dynamic OpenAlex candidates, live official captures, reviewed facts and freshness |
| conversion/venue_compiler | Pandoc/citeproc/Typst/python-docx exports, venue compliance and canonical binding |
| submission_package | Local artifacts, source/submission ZIPs, manifests/hashes and readiness verification |
| publication | Strict final factual attestations, transactional occupied slot, receipt-backed state transitions and immutable event journal |
| preprints | Explicit policy/release review, local public derivatives and separately recorded posting facts |
| revisions | Actual referee excerpts, new same-Study manuscript, verified additional experiments, response letter/change table/diff and immutable response audit |
| revision_submission | Same-journal child package, separate revised factual attestation and confirmed resubmission on the original occupied slot |
| ojs/portal | Official OJS 3.5 API, explicit reviewer-file delivery, remote inspection, durable write intents and receipt-backed final submission |

No agent framework, fixed journal list, migration or provider fallback was added.
Research/licensing: [Phase 1 reuse](reuse-decisions.md), [Phase 2 reuse](phase2-reuse.md),
[Phase 3 reuse](phase3-reuse.md), [Phase 4 reuse](phase4-reuse.md), [document conversion](pdf-reuse.md).

## Phase 1 audit corrections

| Defect | Correction |
| --- | --- |
| Rebuild discarded author edits | Preserve canonical titles/prose; explicit render validates revisions |
| Freeze depended on mutable live records | Independent copied source, records, citations, searches and evidence |
| Copy/setup/interruption left unusable state | Staged validation, atomic publication/SQL transaction, failure diagnostics and retry |
| Timeouts left descendant processes | Terminate process trees; recover abandoned RUNNING attempts |
| Old success hid unresolved latest attempts | Structured readiness issues; valid historical claims remain valid; pending runs block freeze and reviewed failures stay in frozen audit |
| Concurrency and Windows handles | Study/manifest locks, unique atomic JSON writes, bounded Windows publication retries and deterministic SQLite closing |
| Weak path/record/provenance checks | Portable paths, junction/link rejection, normalized source references, pinned run/manifest/executable identity |
| Unrelated AI disclosure and numeric lint | Study-scoped CLI provenance and frozen disclosure; fewer question/identifier/unit false positives |
| DOI punctuation and missing PDF backend | Encoded DOI targets; actual Pandoc → Typst PDF; standalone TeX retained |

These correct the existing working implementation. Experiments remain trusted
subprocesses using the caller's OS permissions, not hostile-code sandboxes.

## Phase 2 safeguards

Discovery captures actual OpenAlex JSON, query, ranks, IDs and time. Source-title
relevance is a candidate lead; manuscript scope fit is an author assessment.
Only explicit keywords leave the workspace. Publisher origins are anchored to
the captured venue; extra origins require reviewed actual official links/redirects.

Policies retain typed facts, exact visible excerpts, named reviewer, raw/readable
captures, UTC time, hashes and immutable receipt. Current journal-specific Clarivate
evidence is required for SCIE/ESCI. Missing/unreachable facts stay unknown. Download
alone never proves interpretation. Captured artifact integrity is checked separately
from readiness, allowing an intact partial policy to produce a blocked package.

Compiler and packager each fetch official pages again. Default TTL is seven days
(configurable 1–30), never a substitute for live refresh. Changed policy between
compile/package, stale receipts, tampering, unapproved redirects and missing facts
block readiness. No manuscript or author information is uploaded for lookups.

Each local candidate pins the same approved scientific freeze and follows
`VENUE_SELECTED → VENUE_COMPILED → SUBMISSION_READY`. Multiple preparation
candidates are not active peer-reviewed submissions. Phase 3 adds the separate
author attestation and receipt-backed journal states below.

The compiler checks article type, sections, word/character/keyword limits,
declarations, AI permission/disclosure and formats. Final PDF manuscript words
are conservatively counted as well as source words, so bibliography expansion
cannot silently exceed a limit. Pandoc citeproc uses verified metadata and supplied
licensed CSL when prescribed. Native PDF/Word numbering and LaTeX instructions
follow policy. Anonymous PDF/DOCX text, metadata and tables are inspected; identifying
references remain author-review blockers. Funding, COI, scope-fit and cover-letter
facts are author inputs, not generated factual attestations.

Packages include real PDF/TeX/DOCX, source ZIP, measured results CSV, figure directory,
evidence map, cover letter, author/venue metadata, declarations, policy evidence,
compliance, manifest and submission ZIP. Each file set/hash and archived byte is
checked. Canonical prose, references, tables and required blockers are independently
recomputed. Administrative identity files and audit supplements must not be uploaded
as anonymous-review material. Blocked outputs remain inspectable with CLI exit 1.

## Phase 3 safeguards

Final author attestation is separate from scientific freeze. All six strict
boolean factual declarations must be true, with the approved author's identity.
The package/freeze/author/declaration hashes and a newly fetched compatible
official policy are pinned in the attestation event. A policy TTL cannot replace
this live refresh; an expired but intact prior capture can be refreshed.

The author attestation reserves the one peer-review slot per Study across its
Papers and candidate venues. `BEGIN IMMEDIATE` checks competing states, appends
the event and updates the submission in one SQLite write transaction. Independent
processes cannot both acquire the slot. Accepted, proof and published records
retain it against duplicate resubmission. Exact approved evidence reused under
another Study ID is also blocked; unrelated measurements on the same project are
allowed. This is conservative evidence-overlap detection, not semantic salami
publication assessment or an author-reviewed related-paper exception workflow.

Receipt events require a nonempty preserved actual file, approved author,
timezone-aware occurrence time, consistent journal manuscript ID and an evidenced
journal/submission-service URL. The imported file is author-confirmed rather than
independently authenticated. Its bytes/hash, structured decision and predecessor
hash form an immutable journal. Missing/orphaned artifacts, deleted index entries,
altered evidence and state/history disagreement block further actions.

`WITHDRAWAL_REQUESTED` retains the slot. Only an actual confirmed withdrawal or
rejection releases it. An unsubmitted author reservation can be explicitly
cancelled; submitted candidates cannot use cancellation. Journal history includes
submission, review, revision, rejection, withdrawal, acceptance, proof and
publication. The revision state now connects to the evidence-linked workflow below.
Historical checks validate preserved policies without requiring them to remain
fresh months later; a new submission attestation still requires live verification.

Preprints have independent `PREPRINT_READY` / `PREPRINTED` records and never clear
the journal slot or assert peer-reviewed acceptance. Preparation requires an
explicit allowed decision tied to captured official preprint evidence and author
posting/release confirmations. An occupied slot binds it to that journal's policy;
an unrelated permissive policy cannot bypass the active journal. Existing posted
facts require an explicit complete preprint-compatibility review before a new
attestation. Registry/artifact reconciliation prevents deleting a posting record
to hide that requirement. Policy and posting audit avoid recursive journal checks.

Public preprint Markdown/TeX/PDF and source ZIP reuse Pandoc/Typst and the approved
canonical renderer. Private author fields and raw experiment artifacts are omitted
from the source ZIP. Server classification, metadata, license eligibility and
server-side source compilation are still unverified; preparation is for local
author review. Existing posting facts can be recorded without claiming permission
to upload, using a separate receipt and approved freeze digest. Prepared posting
receipts must match the chosen server origin.

The journal/preprint guard covers one selected workspace and cannot discover an
unrecorded external submission or coordinate independently copied workspaces.
No new runtime dependency, account, payment, manuscript upload or final Submit was
added. SQLite/Pydantic and existing scientific/policy/conversion modules are reused.
JSON command output now escapes Unicode portably. An actual Windows `cp949`
subprocess regression preserves non-encodable punctuation, emoji and Korean text
without crashing; source/manuscript files remain UTF-8.

## Revision safeguards

Actual author-confirmed referee text/PDF is preserved without altering its raw
bytes. Exact excerpts must match its extracted text and reference targets in the
scientific freeze that was actually submitted for that review round. Review and
response registries reconcile database identities and immutable artifacts. Later
rounds use the last submitted revised child, preserving the original submission
identity and journal manuscript identifier.

A separate Paper within the original Study clones that freeze. Existing approved
papers and initial packages remain immutable. Explicit author section replacements
reuse canonical rendering and numerical/citation evidence checks. Every comment
requires a response and disposition, plus rationale for disagreement or partial
acceptance. Accepted responses must point to an actually changed section. Requested
additional experiments require successful same-Study runs started after the review
and linked verified claims present in the revised manuscript; old runs and prose
promises cannot satisfy the requirement. Unsupported numerical/novelty replies and
inline unverified scholarly citations block readiness. Reviewer quotes are
preserved as observations; scientific values in generated replies come from
verified claims.

Immutable response builds contain the author plan, response letter, change CSV,
regenerated manuscript diff, scientific/hash bindings and optional real PDF/DOCX.
Revised delivery requires separate scientific approval, the same venue/author and
current policy verification. An explicitly reviewed updated same-journal policy
can be selected; following confirmed resubmission, later decision origins and
preprint permission checks use that policy without altering old journal events.
Anonymous-review venues receive a separate redacted Markdown/PDF/DOCX response,
checked for known identity in exported text and metadata. Original author responses,
plans and diffs are retained as administrative files, with immutable file-role
instructions. A revised author attestation reviews all six factual
declarations again. A confirmed receipt moves the original journal from `REVISION`
to `UNDER_REVIEW`; the candidate cannot acquire a second initial-submission slot.
The occupied journal guards evidence from its original, every submitted revision
and any revised author attestation awaiting its receipt, including reuse under
another Study ID. Transactions recheck both slot and evidence overlap.

The ordinary live receipt command cannot bypass revised approval with a direct
`REVISION → UNDER_REVIEW` receipt. Already preserved observations remain auditable.
Historical response/delivery checks validate pinned evidence without recursively
depending on an active revision state or fresh present-day policy.

Local review readiness explicitly reports
`revision_portal_requirements_verified=false`. Existing free-initial-submission
format support does not establish marked manuscript or actual revision upload-field
compliance. A target publisher adapter still needs the selected journal's current
documented portal and authorized author account. No generic upload endpoint or
editorial-decision API is presented as an author submission action.

## Actual verification

Final 0.4.0 full suite: `python -m pytest -q` — **513 passed, 2 skipped**,
1997.76 seconds (33 minutes 17 seconds), with all 515 current cases collected
after the final code and fixture corrections. The two skips are native Windows
symlink-permission cases; junction and other unsafe-path rejection are exercised
separately. This includes 75 additional cases beyond the previous release, covering
actual report import, edited/approved children, requested post-review experiments,
response integrity, anonymous derivatives, updated-policy multiple rounds,
overlap reservations, concurrent receipt handling and failed-write rollback.

Phase 4 actual integration smoke:
`C:/Users/Public/Documents/ESTsoft/CreatorTemp/paperfactory-phase4-smoke-85hkqe2v/phase4-smoke-result.json`.
The original and genuinely executed post-review compression run both succeeded:
459 original bytes, 215 compressed bytes, ratio 0.4684095860566449. The repeated
measurement demonstrates the evidence/revision workflow, not a general benchmark
or independent statistical replication. Method clarification and the repeat-run
request were accepted with applied changes; unsupported generalization was
declined with author rationale. The approved revised paper, response and delivery
passed their audits. The original freeze and initial package remained intact, with
one occupied journal slot and the same external manuscript identifier.

The synthetic double-anonymous venue produced four actual PDFs: original and
revised manuscripts, administrative author response and blinded reviewer response.
Each has two pages. All eight pages were rendered with Poppler and visually
inspected for clipping, overlap, glyphs, duplicated headings and identity leakage.
Known author name/email/affiliation are absent from the reviewer exports; the
administrative original preserves the author. Tampering the response letter,
blinded derivative or imported receipt was detected and then restored. Policies,
authors, decisions and resubmission confirmations are explicitly synthetic;
no account, manuscript upload or real external submission occurred.

Installed 0.4.0 commands verified the new `RESUBMITTED` delivery and historical
approved revision. The prior Phase 1 workspace still reports two successful runs;
the preserved Phase 2 ZIP passes historical verification and Phase 3 withdrawal
and rejection journals remain valid, including their existing observed receipts.

Phase 3 full run: `python -m pytest -q`: **437 passed, 2 skipped**, 843.59 seconds.
The final Windows Unicode-output regression was added after that run's collection;
the subsequent complete CLI subset passed **23 tests** in 41.01 seconds, including
the new regression. That release's collection contained 440 cases: 438 distinct passing
tests and the same two native-symlink permission skips. Lifecycle's 49 tests and
preprint's 29 tests cover threads/processes, expiry, policy/receipt binding,
registry deletion, evidence overlap and failed-commit rollback/retry.

The Phase 2 baseline was 356 passed, 2 skipped in 206.45 seconds on Windows /
Python 3.12.14. The two skips require native symlink creation privileges; junction
and ordinary unsafe-path rejection are exercised independently.

`pip check`: no broken requirements. `compileall`: succeeds. HTTP tests use mock
transport; explicit live API/Git smoke scripts remain separate.

| Path | Actual result |
| --- | --- |
| Local text-study CLI | Corpus 459 bytes, compressed 215 bytes, ratio 0.4684095860566449; successful inventory and separate compression Study |
| Live Crossref fixture query | 2 independently resolved metadata records; no full-text/novelty claim |
| Manuscript CLI | Standalone TeX then actual PDF via render; integrity PASS, 3 measured claims |
| Fresh public Frontron input | Commit 3a7da2822721801db88ea059d204c8c6c622fab4; sanitized 161 files / 1,121,463 bytes; live Crossref, inventory, TeX, integrity PASS |
| Complete synthetic venue/reviewer fixture | Actual compression → scientific test freeze → mocked verified policy → real 2-page PDF/TeX/DOCX → SUBMISSION_READY |
| Live PLOS One | Dynamic discovery, real official homepage/guidelines → PDF and blocked ZIP; unknown rules/indexing retained |
| Live freshness | Initial capture, compiler refresh and package refresh separately recorded; synthetic smoke observes all 6 source requests |
| Package mutation | Altered tables, metadata, manifests, ZIPs and export content detected; smoke restores fixture and revalidates readiness |
| PDF visual QA | Offline/live pages rendered with Poppler and inspected for clipping, overlap, glyphs, tables and numbering |

Frontron's own business tests/desktop workload were not executed. Inventory is
pipeline evidence, not recovery/performance research. Ready-package author/review
and journal policy are conspicuously synthetic fixtures; measurements/exports are
real. The actual PLOS package remains incomplete. No real scientific approval,
preprint upload, account, payment, human data collection or journal submission occurred.

Latest complete Phase 2 smoke: `C:/Users/Public/Documents/ESTsoft/CreatorTemp/
paperfactory-phase2-smoke-2r3k5r0e/phase2-smoke-result.json`. Synthetic ready candidate:
`submission-b717b0fbeaf8`; genuine-policy blocked candidate: `submission-94f748c8fd12`.
The installed `submission check` command verified the ready ZIP with no errors.

Latest Phase 3 smoke: `C:/Users/Public/Documents/ESTsoft/CreatorTemp/
paperfactory-phase3-smoke-0a7r8u47/phase3-smoke-result.json`. It executed actual
corpus compression again (459 original bytes, 215 compressed bytes,
0.4684095860566449 ratio), checked the three raw-linked claims and frozen canonical,
and exported actual PDF/TeX/DOCX for two distinct synthetic journal venues.
Synthetic confirmation history exercised:

`AUTHOR_ATTESTED → SUBMITTED → UNDER_REVIEW → REVISION → UNDER_REVIEW →
WITHDRAWAL_REQUESTED → WITHDRAWN_CONFIRMED`, then the second venue's
`AUTHOR_ATTESTED → SUBMITTED → REJECTED`.

A competing attestation was blocked both initially and while withdrawal was only
requested. Confirmed withdrawal enabled retargeting; confirmed rejection freed
the slot. A separately prepared and recorded synthetic preprint preserved the
occupied peer-review slot. New-venue attestation required its explicit preprint
policy review. Receipt tampering blocked audit and was then restored; both
immutable journal packages remained valid and the scientific freeze unchanged.

The two journal PDFs and separate preprint PDF each contain two pages. All six
pages were rendered with bundled Poppler and visually inspected: no clipped
content or duplicate title/author. Preserved PNGs are in the smoke root's `qa/`
directory. Installed 0.3.0 commands checked the recorded rejection and preprint,
the previous Phase 2 ready ZIP, and the default Phase 1 workspace. All receipts,
policies, identities and posting/submission confirmations in the Phase 3 smoke
are explicitly synthetic; no real external upload or submission occurred.

Outputs remain in external temporary workspaces printed by smoke scripts. The
default demonstration selection was refreshed only if it still pointed to the
earlier generated fixture. No real author data or research assets were committed.
Stricter execution provenance intentionally has no compatibility layer: older
development artifacts lacking pinned run/working-directory records require fresh
ingestion/execution, rather than fabricated verification or migration.

## Scope and next increment

Discovery/writing remain conservative deterministic heuristics/templates. The
inventory is not a publishable study. Substantive questions require project-specific
analysis and scientific interpretation. Literature verification is metadata-only.
Scientific novelty, semantic overlap, exact venue word-count scope and subtle
identifying language require author review. Local hashes cannot prevent a privileged
user from forging the entire store.

The current canonical model has prose/claim/citation blocks. Free initial formats
are supported. Mandatory publisher templates, structured figure/highlight/graphical
abstract requirements and unsupported required supplements remain explicit blockers;
no generic layout is falsely labeled compliant. Policy interpretation is a typed
researcher review. Login/JavaScript-only MJL sources can prevent verified indexing;
no account or undocumented API is used.

The next useful increment is one substantive existing analysis and fully reviewed
real venue, extending only the required figure/supplement/template support. The
revision workflow, additional experiment linkage and response-to-reviewers are
implemented, including rejected-feedback retargeting and an OJS 3.5 initial
submission adapter. Actual target credentials, custom requirements and revision
review-round uploads need verified acceptance. Final external Submit remains an
explicitly authorized author action. ScholarOne, Editorial Manager and arXiv upload
adapters are not implemented.
