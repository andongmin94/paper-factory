# Web workspace, three empirical papers and autonomous research

The implemented scope extends beyond cloud setup: Paper Factory now provides a
Korean web research workspace and three English empirical articles based on
executed experiments against pinned, unchanged production components.

The additional goal is repository-to-manuscript automation without this Codex
chat. The installed `auto` CLI and web workflow coordinate subscription-backed
Codex proposals, isolated generated experiments, deterministic analysis,
inspected literature and grounded native exports. Validation and remaining
runtime prerequisites are recorded in [autonomous research](autonomous-research.md).
The earlier three articles were produced outside that pipeline. They must not be
presented as proof of an autonomous app-generated paper. Actual model requests
in this cloud encountered proxy CONNECT 403 and a later HTTP 401; a successful
live end-to-end autonomous study remains unverified.

## Use the workspace

```bash
paperfactory --env-file .env serve --host 127.0.0.1 --port 8765 \
  --studies /workspace/paper-factory-deliverables/studies \
  --data /workspace/paper-factory-data/web
```

The browser workflow includes GitHub/local project import, research questions,
Python experiment registration and execution, Crossref search/DOI lookup,
manuscript build/edit/render, integrity review and artifact downloads. Persistent
jobs report queued, running, succeeded, failed or interrupted states and retain
their logs. Restarting the server preserves project and job records; it does not
silently repeat unfinished experiments.

Write operations require loopback access and the server's matching origin.
Nonloopback serving is an artifact-only preview. Web experiments use existing
Python scripts from imported source and run with the invoking user's permissions,
not a hostile-code sandbox. The CLI's automatic asset inventory and deterministic
drafting remain distinct from the study-specific analyses and full articles.

The optional `research` installation extra supplies NumPy/Matplotlib for figures.
Native manuscript export additionally uses the `pdf` extra and Pandoc. Each study
records its own pinned runtime and reproduction dependencies.

## Executed studies and delivered evidence

| Study | Pinned source commit | Executed evidence |
|---|---|---|
| **frontron**: whole-set preflight and conflict-preserving recovery | `3a7da2822721801db88ea059d204c8c6c622fab4` | 855 genuinely killed writer processes; 1,305 recovery observations; production versus explicit no-preflight ablation |
| **premiere-ai-harness**: lexical confidence and protected-speech loss | `c73614c3cf551b12fa6cf71952ec12f1cadc64ed` | 1,920 derived synthetic fixtures; 28,800 comparison rows; parser, frame-alignment and runtime controls |
| **music-producer-kit**: preservation contracts in bounded MIDI editing | `c3f1a092d75eb2789bb1d34f40352371821fe4e4` | 108 generated files; 648 timed observations; 101,376 protected target events; 288 invalid-edit refusals |

Each article describes its question, methods, results, comparisons, limitations
and the actual reading status of its references. Protocols and raw data disclose
which observations share a fixture or repeat execution. Seeded synthetic inputs
are not natural conversation samples, user studies, commercial-host acceptance
or estimates of industrial failure prevalence. The MIDI reconstruction is an
explicitly limited representation ablation, not a defect attributed to
`pretty_midi`. Process kills are not power-loss durability tests.

The final artifact set is `paper.md`, `paper.pdf`, `paper.docx`, `paper.tex`, local
bibliography, figures/results, `export-validation.json`, `manifest.json`,
`bundle-inventory.json` and `reproducibility.zip`. The
[export helper](../scripts/build_research_artifacts.py) builds these from the
existing manuscripts, measured results, `study-info.json`, author metadata and
verified bibliography; it does not perform or fabricate the experiments.
PDF/DOCX reopening and optional XeLaTeX compilation have distinct validation
records. Compact bundles retain generators and measured summaries; large case
trees remain in the cloud study directories and can be regenerated.

Application and HTTP/browser checks are recorded separately from the research
results. A working web interaction demonstrates the application's workflow,
without certifying the scientific merit of a paper or the external source
product's completeness.

## Authorship and literature

Author identity belongs in local configuration rather than repository documents.
Copy the blank [.env.example](../.env.example) to `.env`, fill the `PF_AUTHOR_*`
fields and select it explicitly with `paperfactory --env-file .env <command>`.
There is no automatic dotenv lookup. Existing process settings take precedence
over the selected file; explicit author JSON fields take precedence over author
environment values. On Linux/macOS, restrict the private file with `chmod 600 .env`.

The export helper likewise accepts `--env-file .env`; optional `--author <JSON file>`
preserves explicit metadata overrides. Final paper files, manifests and reproduction
bundles include the supplied author identity and correspondence. Moving configuration
to `.env` does not encrypt it or anonymize those outputs. Author metadata does not
assert scientific approval, author attestation, publication or journal submission.

Literature records distinguish actually inspected full text and official
documentation from abstract-only and metadata-only references. DOI existence
alone does not support findings or an evaluation claim. The
`literature/source-verification.json` ledger records permitted claims, unavailable
primary sources and precise reading scope. No full-text review is asserted for
an inaccessible paper.

## Working locations

- Application source: `/workspace/paper-factory`.
- Pinned source checkouts: `/workspace/paper-factory-deliverables/sources`.
- Articles, raw trials and exports: `/workspace/paper-factory-deliverables/studies`;
  [Frontron instructions](/workspace/paper-factory-deliverables/studies/frontron/README.md),
  [Premiere protocol](/workspace/paper-factory-deliverables/studies/premiere-ai-harness/PROTOCOL.md),
  [MIDI instructions](/workspace/paper-factory-deliverables/studies/music-producer-kit/README.md).
- Private author configuration: explicitly selected, Git-ignored `.env`; export
  metadata remains with the external paper artifacts.
- Literature and bibliography: `/workspace/paper-factory-deliverables/literature`;
  [source-reading ledger](/workspace/paper-factory-deliverables/literature/source-verification.json).
- Integration validation: `/workspace/paper-factory-deliverables/validation`.
- Web projects and jobs in the command above: `/workspace/paper-factory-data/web`.

All cloud tasks are already isolated. Use existing checkouts; do not create a Git
worktree unless explicitly requested. Preserve user changes and distinguish
source development from generated research outputs. Local implementation and
artifact completion do not publish the cloud environment or deploy a public
site. External manuscript upload, factual attestations, venue-specific review and
final submission require their own explicitly authorized actions.

Commit only the blank `.env.example` template. Keep real `.env` files, generated
workspaces, web project/job data and private recipient drafts out of GitHub.
