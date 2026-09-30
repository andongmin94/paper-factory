# Paper Factory

Paper Factory is a local, evidence-first research CLI. It connects project
ingestion, study discovery, literature metadata, real experiments, English drafts,
scientific author approval, live venue discovery and policy evidence, venue
compilation, verified local submission packages, author attestations and
receipt-backed publication/preprint tracking (Phases 1–3), and evidence-linked
manuscript revision with local same-journal resubmission bundles and an explicit
OJS 3.5 author submission API adapter.

It does **not** guarantee novelty, scientific correctness, publication quality,
acceptance or complete literature coverage. The automatic study is a descriptive
asset inventory. Substantive research needs an appropriate question, actual
analysis scripts, baselines and scientific interpretation. Journal upload and
final Submit require separate explicit commands and factual author approval.
Preprint upload remains manual.

## Install

Use Python 3.11+ and Git for repository inputs:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\paperfactory.exe --help
```

On Linux/macOS use `.venv/bin/python` and `.venv/bin/paperfactory`. After activating
the environment, use `paperfactory` as below. If Windows points `python` at a Store
alias, use your actual Python executable. This checkout already has a working
`.venv` from implementation validation.

Install [Pandoc](https://pandoc.org/installing.html) for standalone `.tex` output.
Install the optional PDF extra for `manuscript build --pdf` and Phase 2:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev,pdf]"
```

PDF uses Pandoc and the embedded Typst engine; no TeX distribution is required. Without Pandoc,
canonical JSON, Markdown and `compile-command.json` are preserved and the status
is `COMPILE_READY`. Compiler failures preserve the source and fail the command.
Validation used `pypandoc_binary` only to obtain an external Pandoc executable:

```powershell
.venv\Scripts\python.exe -m pip install pypandoc_binary
.venv\Scripts\python.exe -c "import pypandoc; print(pypandoc.get_pandoc_path())"
# Pass that executable to manuscript build --pandoc <path>.
```

Runtime dependencies are Pydantic, Typer, HTTPX and Beautiful Soup; the PDF extra
adds Typst, pypdf and python-docx. Upstream research and licenses are recorded in
[Phase 1 reuse](docs/reuse-decisions.md), [Phase 2 reuse](docs/phase2-reuse.md),
[Phase 3 reuse](docs/phase3-reuse.md), [Phase 4 reuse](docs/phase4-reuse.md) and
[document conversion](docs/pdf-reuse.md) and [OJS API reuse](docs/submission-reuse.md).

## Author environment

Export [.env.example](.env.example) variables in your shell. Real `.env` files are
ignored by Git; the CLI does not automatically load them:

```powershell
$env:PF_AUTHOR_DISPLAY_NAME = "Your actual author name"
$env:PF_AUTHOR_EMAIL = "your-address@example.org"
$env:PF_AUTHOR_AFFILIATION = "Your actual affiliation"
```

Given/family names, ORCID, department, city, country, Scholar ID, GitHub and homepage
are supported. ORCID format/checksum and supplied email/URLs are validated.
Nonempty precedence: explicit `--author-json` fields > individual `PF_AUTHOR_*`
variables > `PF_AUTHOR_PROFILE_JSON` fields > author metadata supplied to the
author API. Identity is never inferred from Git or imported manuscripts.

Freeze requires display name (or given + family), email and affiliation.
Exploratory drafts permit missing metadata with review warnings. Author files
stay in the external workspace. An explicit override must match at approval;
changing identity requires rebuilding and reviewing the draft.

## Start from a local project or Git repository

```powershell
paperfactory start C:\research\my-project
paperfactory status
paperfactory research --list
paperfactory research
paperfactory start https://github.com/andongmin94/frontron
```

Private Git inputs use existing Git credential-manager/SSH configuration; do not
embed credentials in URLs. Code, data (including CSV/JSON/HDF5), scripts, figures,
notes, bibliography, PDF and LaTeX are inventoried as assets. Inventory does not
imply semantic parsing of every format. Git commit and content hashes identify
the imported snapshot, including uncommitted local files.

Sources are copied, with recognized secret files, `.git`, dependency/cache
directories and symlinks/junctions excluded. Originals are never used as experiment
working directories. Default workspaces are under `~/.paper-factory/projects/`;
`~/.paper-factory/current.json` selects the current project. `PF_HOME` changes this
location. Put an explicit `--workspace` before the command:

```powershell
paperfactory --workspace C:\research-workspaces\example start C:\research\my-project
paperfactory --workspace C:\research-workspaces\example status
```

Workspace and source must be separate directories. Nonempty destinations are
rejected. Project, Study, Paper and Submission have distinct identities; Submission
binds an approved canonical freeze, selected venue, policy capture and compiled package.

## Create a study and search related work

`research --list` ranks asset-dependent candidates with question, importance,
unassessed novelty, required evidence/experiments, field, effort and incremental
risk. This is a feasibility heuristic, not a scientific originality assessment.

```powershell
paperfactory research --candidate asset-inventory --domain software_engineering
paperfactory literature search "reproducible software engineering experiments" --limit 5
paperfactory literature doi 10.1038/s41586-020-2649-2
paperfactory research --question "How does lossless compression change the byte length of the supplied text corpus?" --title "A descriptive analysis of corpus compression"
```

Only the supplied search query and returned DOIs go to Crossref. Every citation is
independently resolved; raw metadata, time, URL and hashes are retained. Failed
searches/hits are audited. Imported bibliographies are not silently verified.
Registry verification establishes metadata existence, not full-text findings or
novelty. Empty searches cannot justify a claim of being first.

The inventory candidate gets an immediate experiment plan. A specified substantive
question needs a project-specific manifest; an inventory cannot answer it.
Normalized duplicate questions on the same project are rejected. Semantic
duplicates, translations and salami publication still need author assessment.
Implemented domains are `generic_empirical` and `software_engineering`.

## Run experiments

```powershell
paperfactory experiment run
paperfactory status
```

Each run gets a fresh working copy. Recorded provenance includes original/effective
command, source commit/hash, environment, seed, executable, platform/interpreter,
installed Python package versions, timestamps, exit status, logs, raw outputs and
processed metrics. Only completed successful runs with finite revalidated numeric
outputs produce claims. Failures/timeouts and their outputs remain failures.
Expected outputs inherited from the source are removed before execution.

To use existing analysis scripts, create a JSON manifest using the study ID,
commit and snapshot digest printed by the CLI:

```json
{
  "id": "corpus-compression",
  "study_id": "REPLACE_WITH_STUDY_ID",
  "source_commit": null,
  "source_digest": "REPLACE_WITH_SNAPSHOT_DIGEST",
  "command": ["{python}", "analyze.py"],
  "inputs": ["analyze.py", "corpus.txt"],
  "expected_outputs": ["results.json"],
  "metrics": [{
    "name": "compression_ratio", "output": "results.json",
    "pointer": "/metrics/compression_ratio", "unit": "ratio",
    "description": "Ratio of compressed length to corpus length"
  }],
  "seed": 0, "timeout_seconds": 120, "human_subjects": false
}
```

```powershell
paperfactory experiment register C:\research-plans\compression.json
paperfactory experiment run corpus-compression
```

Paths are relative to the snapshot and command is an argv list, without a shell.
`{python}` selects the invoking interpreter. Selectors are RFC 6901 JSON pointers.
Derived calculations belong in the versioned script. `PF_SEED` is provided, but
the script must actually use it where applicable. Install required scientific
tools/libraries yourself; non-Python environments are not automatically inventoried.

Human-subject flags and recognized participant/user-study/clinical indicators
block automatic execution, even with an approval string. Mark relevant studies
explicitly; keyword detection cannot replace ethics/IRB assessment. Phase 1 has
no automatic human data-collection pathway.

## Build a manuscript and run integrity checks

```powershell
paperfactory manuscript build
paperfactory manuscript build --pandoc C:\tools\pandoc.exe
paperfactory manuscript build --pdf
paperfactory integrity check
```

`--study <id>` selects a study; the latest is the default. One canonical Paper is
maintained per study, independently of venue formatting. Rebuilding preserves
author-edited titles/prose and refreshes evidence/disclosure, invalidating prior review. Workspace outputs include:

- `manuscripts/<paper-id>/canonical.json`: structured sections and record references.
- `manuscript.md`: English draft, Abstract/Results and evidence table.
- `manuscript.tex` or `manuscript.pdf`: actual successful Pandoc output.
- `compile-report.json`: command, status and input/output hashes.
- `author.json`: local author metadata.
- `reports/<paper-id>-integrity.json`: review report in the workspace reports directory.

Each result and table value comes from the same Claim, linked to a successful run,
raw/processed output, JSON selector, analysis script, source version and command.
Result/citation blocks cannot contain free prose. Other prose is conservatively
linted for unsupported numbers, inline citations, novelty, duplicate blocks,
missing sections and limitations. This is not a semantic scientific reviewer.

Review also checks snapshot/raw/provenance/metadata/author tampering, Abstract and
Results consistency, rendered output, compiler input and frozen artifact hashes.
PASS means evidence/metadata consistency; warnings separately identify missing
literature or author assessment. It does not certify submission readiness.
Edit `canonical.json` section prose/title, then run `paperfactory manuscript render`
to validate and render those edits. Direct changes to generated Markdown invalidate
review. Result/citation blocks remain typed references to verified records. An
approved paper is immutable; venue formatting uses a separate derivative.

Latest failed or pending experiments are reported in `experiment_review` and
review warnings. Valid historical measurements remain valid; unresolved running
attempts block freeze, and failed attempts are retained for explicit author review.

Record actual AI assistance before rebuilding:

```powershell
paperfactory record-ai-use "language editing" --tool "Actual tool" --model "Actual model" --input study-id --output edited-section
paperfactory manuscript build
paperfactory integrity check
```

The application makes no LLM calls. Recorded AI activities appear in the draft;
later additions require rebuilding. CLI activities default to the latest study
and may be scoped with `--study`. Frozen papers retain their reviewed activities;
venue disclosure is generated from those activities and verified current policy.

## Target a venue and build a package

First complete the scientific author approval below. Discovery sends only explicit
field/topic keywords to OpenAlex; its source-title search order is a candidate
queue, not manuscript-fit or acceptance certification. There is no hardcoded
journal list. Choose keywords appropriate to the locally reviewed manuscript.

```powershell
paperfactory venue discover "computer science" --limit 5
paperfactory venue show VENUE_ID
paperfactory venue policy init VENUE_ID --source https://publisher.example/journal/guidelines
paperfactory venue policy schema
```

Edit the generated specification with typed facts, exact visible official-source
excerpts, interpretation and the actual reviewer. `policy init` supplies no guessed
facts. [Policy evidence guidance](docs/phase2-reuse.md) explains all fields and
includes a partial live example. SCIE/ESCI requires current journal-specific
Clarivate evidence. Fetch failure, inaccessible indexing, missing facts, expired
captures and changed source excerpts remain `review_needed`.

```powershell
paperfactory venue policy verify VENUE_ID C:\research-workspaces\example\policy-specs\VENUE_ID.json
paperfactory venue policy show POLICY_ID
paperfactory venue select VENUE_ID --policy POLICY_ID --paper PAPER_ID
paperfactory submission settings SUBMISSION_ID
```

Fill the generated settings with article type, keywords, actual scope-fit and
cover letter, and author declarations matching the policy names (funding, COI,
data/code availability, contributions, AI disclosure, etc.). No funding/COI facts
are invented. When a citation style is prescribed, supply its local CSL file,
source URL and license. Empty statements and TODO/TBD declarations block readiness.

```powershell
paperfactory submission compile SUBMISSION_ID C:\research-workspaces\example\submission-settings\SUBMISSION_ID.json --pandoc C:\tools\pandoc.exe
paperfactory submission package SUBMISSION_ID
paperfactory submission check SUBMISSION_ID
paperfactory status
```

Compilation and packaging each **fetch official policy pages again**. Selection
pins the scientific freeze; compilation checks that identity/evidence has not
changed, checks venue requirements and creates actual PDF, LaTeX and DOCX. Native
PDF and Word line/page numbering and LaTeX numbering instructions follow the policy. Known author identities are removed
for anonymous review; self-identifying references or PDF text/metadata are flagged.

The local package includes manuscript exports, source ZIP, measured results CSV,
figure directory (explicitly no figures for the current numeric-only canonical
model), evidence-map supplement, cover letter, author/venue metadata, declarations,
policy captures, compliance report, manifest and `submission.zip`. Every artifact
and every archived member is hashed and checked. The package README identifies
accepted manuscript formats and separates review files from administrative files.
Do not upload the entire administrative archive as an anonymous-review document.

Incomplete policies still produce inspectable **blocked** outputs and exit with
code 1. Only a complete, fresh, compatible policy and passing artifacts permit
`VENUE_SELECTED → VENUE_COMPILED → SUBMISSION_READY`. An altered official policy
requires a new selection/compile; immutable candidates are not overwritten. The
compiler currently supports free-format initial submission. Mandatory exact
publisher templates or required supplements outside the current numeric-only
model are reported as blockers. Full semantic policy interpretation remains an
explicit researcher review, not a claim inferred from downloading a web page.

## Author approval and publication-state rules

After examining the evidence, actual related work, limitations and identity:

```powershell
paperfactory manuscript approve --approve --assessment "My assessment of related work, novelty, limitations and scientific responsibility."
```

Freeze requires a passing fresh review, recorded successful search, complete
matching author information and a nonempty assessment. It preserves a hash-bound
local archive of manuscript, source and referenced evidence. Rebuilding is blocked
and frozen changes fail review. Frozen review uses its copied records and
artifacts independently of mutable live workspace data. It is not protection against an administrator
deliberately rewriting both database and artifacts.

Study states cover planned, experiments running and evidence ready, with further
runs allowed. Paper states cover drafted → integrity checked → explicitly author
approved; failed review reverts an unfrozen draft. Invalid transitions are rejected.

The final package has a separate factual author attestation:

```powershell
paperfactory submission attestation <submission-id> --output attestation.json
# Review the package; set all six factual declarations to true only when correct.
paperfactory submission attest <submission-id> attestation.json --approve
paperfactory submission attestation-schema
paperfactory submission history <submission-id>
```

The approved author's identity must match the frozen manuscript. Attestation
refetches official policies and binds the package, author metadata, declarations
and current policy. It requires all authors' approval and confirmation that the
paper is not under review elsewhere, and that COI, funding, AI disclosure and
author information are correct. Unknown, false or string-valued answers block it.
If preprints have already been posted, a separate `preprint_review` must list them
and explicitly confirm compatibility using this venue's current official evidence.

`AUTHOR_ATTESTED` reserves the Study's one peer-review slot across its Papers and
venue candidates. The reservation and competing-state check are committed in a
single SQLite write transaction. Preparing multiple packages is allowed; a second
attestation is blocked while the first is reserved, submitted, under review, in
revision or awaiting withdrawal confirmation. Acceptance, proof and publication
also retain the guard against resubmitting the same Study.

Record actual external events using structured facts plus the actual receipt:

```powershell
paperfactory submission receipt-schema
paperfactory submission record-receipt <submission-id> event.json actual-decision.txt --confirm
paperfactory submission history <submission-id>
```

The JSON specifies `target_state`, `external_id`, `external_url`, `occurred_at`,
`verified_by` and `note`. Use the schema for allowed states and validation. The
external manuscript identifier stays consistent across that submission's events.
Receipts and events are preserved with hashes in an append-only journal; changes,
missing events or a disagreement with stored submission state block new actions.
These are author-confirmed imported documents, not authenticated editor messages.

The supported journal lifecycle is `SUBMITTED → UNDER_REVIEW → REVISION`, with
confirmed rejection or withdrawal permitting retargeting. A
`WITHDRAWAL_REQUESTED` event retains the active slot; only
`WITHDRAWN_CONFIRMED` releases it. `REJECTED` likewise requires an actual decision
receipt. Acceptance can progress through `PROOF → PUBLISHED`. A local reservation
that was never submitted can be cancelled with `submission cancel-attestation
<id> --actor <approved-author> --reason <reason>`; a submitted candidate cannot
use this cancellation path. Historical receipt checks remain usable after the
policy TTL expires; a new attestation always refetches current rules.

The guard covers the selected workspace. It cannot detect an unrecorded outside
submission or coordinate separately copied workspaces; the author's elsewhere
declaration remains necessary. Exact approved measurements reused by another
active or published manuscript also block attestation, even under a new Study ID.
Full scientific overlap/salami assessment remains an author responsibility.
No final Submit or external manuscript upload occurs.

## Separate preprint workflow

```powershell
paperfactory preprint settings --paper <paper-id> --policy <policy-id> --output preprint.json
# Review official preprint rules, posting permission, server and license.
paperfactory preprint prepare preprint.json --approve --pandoc C:\tools\pandoc.exe
paperfactory preprint schema
paperfactory preprint record posted.json actual-server-receipt.txt --confirm
paperfactory preprint check <preprint-id>
```

Preparation requires an explicitly reviewed `allowed` decision tied to the target
venue's captured preprint-policy evidence, the approved author's confirmation and
a fresh official-policy check. Forbidden, unknown, changed or unverified policies
block preparation. Generated files are local review artifacts; server-specific
processing requirements must still be checked before the author's actual upload.
An occupied journal slot binds preparation to that journal's policy; a different
permissive venue cannot authorize a preprint while that journal is active.

`PREPRINT_READY` and `PREPRINTED` are separate records from journal submissions.
A preprint never establishes peer-reviewed acceptance or clears the active slot.
An already-posted preprint can be recorded as an observed external fact without
claiming that Paper Factory authorized its upload. Such a record requires a
matching approved content digest, actual posting receipt and author confirmation;
its report distinguishes observed posting from preparation permission.

## Revise a manuscript and respond to reviewers

First record the actual journal decision as `REVISION`. A review specification
names the approved author, each comment's exact excerpt and its original
manuscript sections, claims or experiments. Preserve the actual UTF-8 report or
text-extractable PDF separately; scanned reports require author transcription.

```powershell
paperfactory revision schema
paperfactory revision import <submission-id> review.json actual-referee-report.pdf --confirm
paperfactory revision draft <revision-id>
paperfactory revision plan <revision-id> --output response-plan.json
# Fill author replies, dispositions, rationale and section replacements.
# If needed, run a real same-Study experiment and link its new run/claims.
paperfactory revision experiment <revision-id> additional-experiment.json
paperfactory revision apply <revision-id> response-plan.json
paperfactory integrity check --paper <revised-paper-id>
paperfactory revision response <revision-id> response-plan.json --pandoc C:\tools\pandoc.exe
paperfactory manuscript approve --paper <revised-paper-id> --approve --assessment "Actual scientific review."
paperfactory revision response-check <response-id> --approved
paperfactory revision submission prepare <revision-id> submission-settings.json --response <response-id> --pandoc C:\tools\pandoc.exe
paperfactory revision submission attestation <delivery-id> --output revised-facts.json
# Review the revised local bundle, actual portal instructions and all six facts.
paperfactory revision submission attest <delivery-id> revised-facts.json --approve
# After the author's actual external resubmission, import its confirmation.
paperfactory revision submission record <delivery-id> receipt.json actual-confirmation.txt --confirm
paperfactory revision submission check <delivery-id>
```

The revised manuscript has a new Paper ID within the same Study. The submitted
freeze and initial package remain unchanged. Each response must cover one actual
comment, retain its original target and describe an applied change or a justified
disagreement. Additional experiments require genuine successful post-review runs
and raw-linked claims present in the revised manuscript. Pending replies, invented
excerpts, unapplied edits and unsupported numerical replies block readiness.

Response artifacts include `letter.md`, a section/evidence change table, the
canonical manuscript diff and hash bindings; Pandoc additionally exports PDF and
DOCX. Anonymous-review venues receive a separate redacted reviewer response;
the original response, author plan and diff remain administrative audit files.
The delivery's readme identifies their roles, and both exported text and metadata
are checked for known author identifiers. A separate immutable delivery binds the scientifically approved child,
verified response and local ZIP. Fresh revised author attestation and a confirmed
receipt advance the **original** journal manuscript to `UNDER_REVIEW`, preserving
its external identifier and occupied slot. An ordinary receipt command cannot
bypass this revised approval path. Later rounds start from the last submitted
revised freeze. Historical artifact audits remain available after a round closes.
If official requirements changed, review them with `venue policy verify` and pass
that same-journal policy ID with `revision submission prepare --policy <id>`.
After confirmed resubmission, subsequent decisions and preprint permission checks
use the revised policy while preserving the original event's policy evidence.

Local readiness does not verify a journal's revision upload fields or marked
manuscript requirements. The OJS adapter supports initial submission files;
revision upload requires the actual review round and remains manual. These
requirements remain explicit in the delivery report.

After a confirmed `REJECTED` decision, the same `revision import/draft/plan/apply`
commands preserve the actual feedback and create a distinct manuscript in the
same Study. Approve that child scientifically, then use ordinary venue selection,
compilation, packaging and attestation for the next journal. The rejected freeze
and journal history remain intact. Another active submission blocks feedback edits.

## Explicit OJS 3.5 submission

Use the actual journal's author account and API bearer token. The journal must
permit author API access and use the reviewed OJS 3.5 protocol. The adapter does
not detect or certify an installation's version: configure it after checking the
journal. Existing HTTPX handles TLS, public DNS validation and bounded responses;
the API token is read from the environment and is never stored in the workspace.

```powershell
paperfactory submission portal schema
# Supply actual journal context, section, locale and manuscript genre IDs.
paperfactory submission portal settings <submission-id> --api-url https://journal.example.org/index.php/journal/api/v1 --section 2 --locale en --genre 1 --output portal.json
paperfactory submission portal prepare <submission-id> portal.json
$env:PF_OJS_API_TOKEN = "<actual-journal-author-token>"
# Review the immutable plan before authorizing remote draft creation/upload.
paperfactory submission portal upload <portal-id> --upload
paperfactory submission portal inspect <portal-id>
```

Uploads are restricted to the ready package's designated reviewer files. The
whole archive, evidence maps and identity-bearing administrative files are not
automatically uploaded. Verify the journal's actual genre visibility; complete
contributors, administrative material and journal-specific forms in its UI.
`--remote <actual-draft-id>` on `portal settings` attaches an existing draft.

Inspect the actual remote title, abstract, keywords, contributors, file identities,
genres and checklist. The inspection returns a `review_sha256` binding those facts.
Fill the six declarations generated by `submission attestation`, then explicitly
authorize final submission only after reviewing both the package and remote facts:

```powershell
paperfactory submission attestation <submission-id> --output attest.json
paperfactory submission portal submit <portal-id> attest.json --review-sha256 <inspected-hash> --approve --submit
# Add --confirm-copyright only after reviewing and accepting the journal's terms.
paperfactory submission portal check <portal-id>
paperfactory submission history <submission-id>
```

The final command refreshes official policy, validates current author/preprint
facts, reserves the Study's sole slot and writes a durable intent before the API
request. A fresh provider read must confirm the submitted date and identity before
local `SUBMITTED` is recorded. A timeout or ambiguous response blocks repeat writes
and cancellation; use `portal reconcile <portal-id> --actor "<approved author>"`
to read the actual result without resubmitting. Uncertain uploads require journal
inspection and remain blocked. Definite provider validation rejection can release
an unused reservation. OJS supplies no conditional atomic lock against another
person changing the draft between our final inspection and its Submit operation.
If a failed local commit leaves preserved event evidence, inspect it and use
`portal reconcile <portal-id> --actor "<approved author>" --recover-local --confirm`.
Recovery validates and imports the next immutable events, then reads the journal;
it never repeats a remote upload or Submit.

This adapter has official-source contract tests and a synthetic provider smoke;
an authenticated acceptance run against your actual journal has not been performed.
ScholarOne, Editorial Manager and arXiv upload adapters are not implemented.

## Verify the working path

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\smoke.py
.venv\Scripts\python.exe scripts\smoke.py --query "lossless text compression zlib" --pandoc C:\tools\pandoc.exe
.venv\Scripts\python.exe scripts\repository_smoke.py https://github.com/andongmin94/frontron --query "desktop software architecture recoverability" --pandoc C:\tools\pandoc.exe
.venv\Scripts\python.exe scripts\phase2_smoke.py --pandoc C:\tools\pandoc.exe
.venv\Scripts\python.exe scripts\phase2_smoke.py --live --pandoc C:\tools\pandoc.exe
.venv\Scripts\python.exe scripts\phase3_smoke.py --pandoc C:\tools\pandoc.exe
.venv\Scripts\python.exe scripts\phase4_smoke.py --pandoc C:\tools\pandoc.exe
.venv\Scripts\python.exe scripts\portal_smoke.py --pandoc C:\tools\pandoc.exe
```

The fixture executes `examples/text-study/analyze.py` on actual included text
bytes. Its results demonstrate plumbing, not a general benchmark. Smoke artifacts
stay in a new external temporary workspace, whose preserved paths are printed.
Default tests use mock HTTP transport; explicit live API/Git scripts are separate.
Phase 2 smoke uses a conspicuously synthetic author/review and fully mocked journal
policy to verify readiness; its corpus measurements and exported PDFs are real.
`--live` additionally discovers PLOS One, captures actual official guidelines and
produces a blocked package with unknown requirements rather than inventing indexing.
See [status](docs/status.md) for actual results and pending requirements.

## Security/privacy and limitations

State and assets stay local outside application/source repositories. No private
input is automatically published or sent to an LLM. Git contacts the selected host;
literature sends explicit query/DOI data to Crossref, venue search sends explicit
keywords to OpenAlex, and policy verification fetches public official URLs. No
manuscript or author profile is uploaded to these services. Secret exclusion is name-based
and cannot discover every embedded credential. No password, MFA recovery-code or
payment storage is implemented; Git uses its existing OS credential manager/agent.

Experiments are trusted subprocesses with the invoking user's OS permissions.
Fresh copies, path checks and minimal environment protect against ordinary
accidental source writes; they are **not a sandbox** for hostile scripts. Use a
disposable VM/container for untrusted code. Arbitrary inherited tokens and author
variables are excluded, but scripts can read/print data accessible to that user.
Back up the SQLite database and artifact directory together. No migrations exist. This audit tightened execution provenance; older development
workspaces without pinned working-directory/run records must be freshly ingested
and re-executed rather than treated as compatible verified evidence.

The next valuable increment is exercising a substantive existing analysis with
full-text related-work assessment and one fully reviewed target venue. The
evidence-linked revision and OJS initial submission workflows are implemented.
Journal-specific revision upload requirements and authenticated acceptance against
an actual target remain to be verified. All final attestations and final Submit
remain explicit human actions; no actual journal submission was performed during
development. See [status](docs/status.md)
for the implemented safeguards, measured verification and remaining limits.
