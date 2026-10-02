# Paper Factory

Paper Factory is a Windows desktop and local web research workspace with an evidence-first CLI. The Korean
web interface supports project import, study creation, experiment execution,
literature lookup, manuscript editing and artifact downloads. An autonomous
workflow calls the official Codex CLI with ChatGPT subscription authentication
to propose research, generate isolated experiments and write grounded manuscripts.
An independently audited native Windows batch produced seven English paper
drafts with reproducible results. Papers and audit outputs remain external
deliverables, not files shipped with a fresh installation.
The CLI also connects project ingestion, study discovery, literature metadata,
real experiments, English drafts,
scientific author approval, live venue discovery and policy evidence, venue
compilation, verified local submission packages, author attestations and
receipt-backed publication/preprint tracking (Phases 1–3), and evidence-linked
manuscript revision with local same-journal resubmission bundles and an explicit
OJS 3.5 author submission API adapter.

It does **not** guarantee novelty, scientific correctness, publication quality,
acceptance or complete literature coverage. The original `research` command's
automatic study is a descriptive asset inventory. The `auto` workflow requires
a feasible production component, independent oracle, comparator, inspected
literature and actual observations, and blocks when these cannot be established. Journal upload and
final Submit require separate explicit commands and factual author approval.
Preprint upload remains manual.

## Windows desktop

The Electron application uses the
[create-frontron template](https://github.com/andongmin94/frontron/tree/main/create-frontron)
and actual source components from
[neobrutal-ui](https://github.com/andongmin94/neobrutal-ui).
The Windows x64 installer and portable application bundle Python, Node.js, the
official Codex CLI, Git, Pandoc, Typst and research dependencies. End users do not
need to clone this repository or install developer tools.

Open **Paper Factory**, connect a ChatGPT subscription through the official Codex
device login, verify the connection, then enter a GitHub repository and research
goal. The app shows saved progress, stop/resume controls and paper downloads.
Connection verification makes one model request against the subscription.
There is no Paper Factory signup, member database or central account service.
Official credentials remain in the app's private local CLI profile; research
records and papers remain local. **Codex 로그아웃** removes credentials from
the selected and current pending app profiles and prevents fallback to another
installed Codex account.
Stop research before changing accounts or logging out. Closing the app requests
research cancellation and waits for worker cleanup; saved results are retained.

Developer builds and the runtime bundling procedure are documented in
[desktop setup](docs/desktop.md). Built installers are under `desktop/output/`.
Code signing is not configured; a local build alone does not create or publish a
GitHub Release.

## CLI and browser installation

Use native **Windows**, Python 3.11+ (3.12 recommended), Git, and Node.js 24 with
npm. Generated research experiments use Windows AppContainer isolation and a
Job Object with resource limits. Windows does not require Docker, WSL2 or a
research image. Run these commands in PowerShell from the cloned repository:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,pdf,research,automation]" pypandoc_binary -r scripts/research-runtime-requirements.txt
npm.cmd install --prefix .venv/codex --no-audit --no-fund @openai/codex@0.160.0
$env:PYPANDOC_PANDOC = (& .\.venv\Scripts\python.exe -c 'import json; from pathlib import Path; import pypandoc; p = Path(pypandoc.get_pandoc_path()); print(json.dumps(str(p if p.is_file() else p.with_suffix(".exe"))))') | ConvertFrom-Json
Copy-Item .env.example .env
.\.venv\Scripts\paperfactory.exe --help
```

Use `python -m venv .venv` if the Python launcher is unavailable. Fill author
settings in the private `.env` locally. The official CLI handles subscription
credentials; do not put API keys or OAuth tokens in that file. These commands use
the virtual environment directly and do not require PowerShell activation.
Repeat the `PYPANDOC_PANDOC` assignment in a new terminal if Pandoc is not on `PATH`.
The [Windows setup helper](scripts/setup_windows.ps1) creates the virtual
environment and installs its dependencies and private Codex CLI. The manual
commands above install Codex inside `.venv/codex` and leave any existing global
CLI unchanged. `PF_CODEX_BIN` is optional: the controller detects that private
installation in its own virtual environment, then checks `PATH`. On Windows it
resolves the official npm launcher to Node and its `codex.js` entry point without
invoking a shell.

The base CLI also supports Linux/macOS. Linux autonomous experiments use the
separate Docker runtime described below; the image builder is a Linux-only
provisioner. PDF uses
[Pandoc](https://pandoc.org/installing.html) and the embedded Typst engine; no TeX
distribution is required. Without Pandoc,
canonical JSON, Markdown and `compile-command.json` are preserved and the status
is `COMPILE_READY`. Compiler failures preserve the source and fail the command.
`pypandoc_binary` provides an external Pandoc executable:

```powershell
.venv\Scripts\python.exe -m pip install pypandoc_binary
$env:PYPANDOC_PANDOC = (& .\.venv\Scripts\python.exe -c 'import json; from pathlib import Path; import pypandoc; p = Path(pypandoc.get_pandoc_path()); print(json.dumps(str(p if p.is_file() else p.with_suffix(".exe"))))') | ConvertFrom-Json
# Pass $env:PYPANDOC_PANDOC to manuscript build --pandoc.
```

Runtime dependencies are Pydantic, Typer, HTTPX, Beautiful Soup, python-dotenv and JSON Schema validation; the PDF extra
adds Typst, pypdf and python-docx. The optional `research` extra adds NumPy and
Matplotlib for study figures; individual study protocols specify their own pinned
runtimes and dependencies. Install all development/export/figure extras with
`python -m pip install -e ".[dev,pdf,research,automation]"`; `automation` adds
the pinned Mido dependency for the optional MIDI research runtime.
Upstream research and licenses are recorded in
[Phase 1 reuse](docs/reuse-decisions.md), [Phase 2 reuse](docs/phase2-reuse.md),
[Phase 3 reuse](docs/phase3-reuse.md), [Phase 4 reuse](docs/phase4-reuse.md) and
[document conversion](docs/pdf-reuse.md) and [OJS API reuse](docs/submission-reuse.md).

## Open the web workspace

After installation, run in PowerShell:

```powershell
.\scripts\start_windows.ps1
# With private author configuration: .\scripts\start_windows.ps1 -EnvFile .env
# Direct CLI invocation after setting PYPANDOC_PANDOC:
.\.venv\Scripts\paperfactory.exe --env-file .env serve --host 127.0.0.1 --port 8765
# Optional: allow local projects below additional directories.
# .\.venv\Scripts\paperfactory.exe --env-file .env serve --source-root C:\research --source-root D:\projects
```

Open `http://127.0.0.1:8765` in a browser on that machine. A fresh clone has an
empty study library; paper files and earlier study folders are external
deliverables and are not included in Git. Pass an existing exported study folder
to `--studies` to browse its papers and results. In **새 프로젝트**, import a
GitHub HTTPS repository, create a research question, register/run a Python
experiment from the imported source, look up literature, then build/edit/render
a manuscript and inspect its integrity report. Jobs preserve their logs and
success/failure state; unfinished jobs are marked interrupted after restart.
The default study library and web data live under `~/.paper-factory`; `PF_HOME`
can select a different external root. Local web imports accept project folders
below your home directory by default. Repeat `--source-root` to set explicit
allowed parent directories. Authentication stores, internal web data and linked
paths remain excluded. The CLI also accepts `paperfactory start <local-project>`.

Research writes require a loopback connection with the server's matching origin.
A nonloopback bind exposes an artifact-only preview. Registered web experiments
execute existing imported Python scripts in separate working copies, with the
invoking user's permissions. They are not a hostile-code sandbox. Automatic
inventory and template drafting remain available; project-specific analysis and
scientific interpretation supply substantive research.

## Autonomous research with a subscription CLI

In the web's **자동 연구** view, import a repository or request up to three
recommendations from a public GitHub account. Supply a goal and budget, then
start the research worker. Progress, cancellation, resumption, account/network
blockers and final artifact downloads are available in that view. Interrupted
autonomous jobs resume verified checkpoints after the server restarts; explicit
cancellations and account/network blockers require deliberate resumption.

Use **ChatGPT 구독으로 연결** in the web automatic-research view to start the
official Codex device login. Open the official link and enter the one-time code,
then click **실제 모델 요청 확인**. Only a successful model response selects the
new account for research. An earlier connection remains selected until that
check passes. Login credentials stay in a private official CLI store outside Git;
Paper Factory reads only its nonsecret connection metadata. No OpenAI API key is
required. Configure the optional trusted CLI path/model in the explicit private
dotenv file. Generated programs never receive this login, author settings or
other controller credentials. Every model call enforces ChatGPT authentication,
including resumed research; API-key authentication blocks generation.
Windows selects a native AppContainer worker,
denies network capabilities, stages read-only source/code/runtime files, and
uses a Job Object to bound and stop its process tree. If that boundary is
unavailable, research blocks instead of running an unrestricted experiment.
Dependencies available to generated programs are explicitly vetted; installing
a package in the controller's virtual environment does not automatically expose
it to an experiment. `auto doctor` reports the available runtimes and packages.

For Windows, check the installation and connect your account:

```powershell
.\.venv\Scripts\paperfactory.exe --env-file .env auto doctor
.\.venv\Scripts\paperfactory.exe --env-file .env auto login
.\.venv\Scripts\paperfactory.exe --env-file .env auto connection
.\.venv\Scripts\paperfactory.exe --env-file .env auto run https://github.com/OWNER/REPOSITORY
```

For Linux autonomous execution, install the same extras in a Python 3.12 virtual
environment, install Node 24 and `@openai/codex@0.160.0`, and provision a Docker
research image. The following Linux-only example includes standard-library
Python/Node and Mido; it does not install arbitrary project dependencies:

```bash
python scripts/build_autonomous_image.py \
  --mido-site-packages "$(python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" \
  --manifest "$HOME/.paper-factory/research-image.json"
```

On Linux, replace the blank `PF_RESEARCH_IMAGE=` in `.env` with the printed immutable
`PF_RESEARCH_IMAGE=sha256:...` value. For the vetted application dependencies,
install [the pinned runtime requirements](scripts/research-runtime-requirements.txt)
with `python -m pip install -r scripts/research-runtime-requirements.txt`, then
add `--with-application-dependencies` when rebuilding the image.
Windows ignores `PF_RESEARCH_IMAGE` and does not run this image builder. Its
optional vetted Python package groups use the same pinned requirements; install
them with `.\.venv\Scripts\python.exe -m pip install -r scripts/research-runtime-requirements.txt`
when the proposed study needs those modules.

```bash
paperfactory --env-file .env auto doctor
paperfactory --env-file .env auto login
paperfactory --env-file .env auto connection
paperfactory --env-file .env auto run https://github.com/andongmin94/madi \
  --goal "Evaluate apps/desktop/src/renderer/llm/proposalDiff.ts:createLlmProposalReview for Unicode reconstruction and bounded fallback with seeded fixtures, a declared comparator and an independent oracle"
paperfactory --env-file .env auto select https://github.com/OWNER --count 3
paperfactory --env-file .env auto batch OWNER --count 3
paperfactory --env-file .env --workspace /path/to/workspace auto status
paperfactory --env-file .env --workspace /path/to/workspace auto resume PIPELINE_ID
paperfactory --env-file .env --workspace /path/to/workspace auto verify PIPELINE_ID
```

`auto login` displays the official approval URL and one-time code, waits for
your approval, then verifies an actual model response. Alternatively, use the
web connection button and its separate model-check button. Use `auto probe` to
recheck model access and `auto logout` to remove the app-owned connection.
Small Node repositories
such as [madi](https://github.com/andongmin94/madi),
[garak](https://github.com/andongmin94/garak) and
[mini-cast](https://github.com/andongmin94/mini-cast) provide production components
for the initial runtime; feasibility checks still determine whether each proposed
study can execute with its available dependencies.

Successful runs export PDF, DOCX, standalone TeX, Markdown, tables, figures,
measured observations and a reproducibility ZIP. Numerical statements and
citations use checked evidence references; a failed scientific control retains
its results and stops rather than generating more favorable observations.
Source-call traces detect an accidentally substituted implementation. They are
not an adversarial proof of truthful measurements, and their timing overhead is
disclosed in the protocol and manuscript.

The integration/native-export tests use explicit model and observation fixtures.
The 2026-10-01 native Windows batch also exercised actual subscription requests,
isolated source execution, literature retrieval and document exports. Seven of
thirteen selected repositories yielded audited drafts; unsuccessful or invalid
studies were retained and excluded from the final paper package. This finite
check does not guarantee future model access or scientific validity for another
repository. The login flow uses a fresh private worker profile and preserves
other installed applications' authentication. Device approval requires the
account owner.
See [setup, evidence and recovery instructions](docs/autonomous-research.md).

## Three executed empirical studies

These output folders are external deliverables, not files in the repository.
The validation cloud used `/workspace/paper-factory-deliverables/studies`;
local clones do not create or download that directory. Each study pins its unchanged
production source and retains experiment scripts, raw results, summaries,
figures, an English manuscript and reproduction instructions.

| Repository | Executed study | Main evidence |
|---|---|---|
| [frontron](https://github.com/andongmin94/frontron) | Process-failure recovery and whole-set conflict preflight | 855 killed writers; 1,305 recovery observations |
| [premiere-ai-harness](https://github.com/andongmin94/premiere-ai-harness) | Transcript editing: recovery of expendable time versus protected speech | 1,920 derived synthetic fixtures; 28,800 comparison rows |
| [music-producer-kit](https://github.com/andongmin94/music-producer-kit) | Bounded MIDI edits and preservation of non-target events | 108 fixtures; 648 timed calls; 288 invalid-edit refusals |

When you have those deliverables, open each study's `README.md` or `PROTOCOL.md`
for the recorded environment and exact reproduction commands.

The web catalog links each study's `paper.md`, `paper.pdf`, `paper.docx`,
`paper.tex`, bibliography, results, export validation and `reproducibility.zip`.
The study protocol explains which large generated case files are regenerated
instead of included in the compact bundle. See the
[development goal and evidence locations](docs/development-goal.md).

The [research export helper](scripts/build_research_artifacts.py) reads actual
manuscripts, `study-info.json`, user-confirmed author metadata and the verified
CSL bibliography. It exports native files, reopens PDF/DOCX, records hashes and
builds the web manifests and compact bundles:

```bash
python scripts/build_research_artifacts.py \
  /path/to/studies \
  --env-file .env \
  --bibliography /path/to/bibliography.json
```

The helper reads author fields from the explicitly selected environment file.
An optional `--author <JSON file>` supplies explicit author fields with precedence
over environment values and remains compatible with existing export commands.
Use `--pandoc <executable>` to select the installed Pandoc binary; optional
`--compile-tex` additionally validates standalone TeX with XeLaTeX. Exporting does
not rerun experiments or assert scientific approval. Literature provenance
distinguishes inspected full text, inspected abstracts and metadata-only records.
The studies use controlled generated inputs: their results do not establish
natural-recording error rates, musical quality, native Adobe/Ableton acceptance,
power-loss durability, publication or journal acceptance.

## Author environment

Copy the blank [.env.example](.env.example) to `.env` and fill your actual author
metadata locally. On Linux/macOS:

```bash
cp .env.example .env
chmod 600 .env
# Edit .env, then explicitly select it before the command:
paperfactory --env-file .env status
paperfactory --env-file .env manuscript build --pdf
```

On Windows, use `Copy-Item .env.example .env` and restrict the file to your account.
There is no automatic `.env` discovery. Existing process environment bindings,
including empty ones, take precedence over values in the selected file. You may
also export `PF_AUTHOR_*` variables directly in your shell without `--env-file`.

Given/family names, ORCID, department, city, country, Scholar ID, GitHub and homepage
are supported. ORCID format/checksum and supplied email/URLs are validated.
Nonempty precedence: explicit `--author-json` fields > individual `PF_AUTHOR_*`
variables > `PF_AUTHOR_PROFILE_JSON` fields > author metadata supplied to the
author API. Identity is never inferred from Git or imported manuscripts.

Freeze requires display name (or given + family), email and affiliation.
Exploratory drafts permit missing metadata with review warnings. Author files
stay in the external workspace. An explicit override must match at approval;
changing identity requires rebuilding and reviewing the draft.

Git ignores real `.env` files and keeps only the blank `.env.example` template.
Keep generated workspaces, web project/job data and private recipient drafts out
of source commits. A dotenv file is plain text, not encryption: generated papers
and their reproduction bundles still include the author identity and correspondence
required for those artifacts. Review that information before sharing the outputs.

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

The web workspace and three executed studies are documented in
[development goal](docs/development-goal.md). Scientific author review and a
fully reviewed target venue remain separate from completing these local
artifacts. The evidence-linked revision and OJS initial submission workflows are
implemented; journal-specific revision uploads and authenticated acceptance
against an actual target remain to be verified. Final attestations and Submit
remain explicit human actions. No actual journal submission was performed during
development. See [status](docs/status.md) for the earlier CLI verification and
remaining venue-integration limits.
