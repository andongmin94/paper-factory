# Repository URL to one draft bundle

Use this procedure for a **new repository-to-draft request**, not every continuation or file-preparation task. Follow the evidence, preservation and human-review boundaries in [SKILL.md](../SKILL.md). The agent reads, selects and writes; the commands below operate on those materials.

## 1. Capture and read

Inspect the tracked tree and local instructions before choosing files. Read the README, relevant implementation, tests and any retained experiments. Work in a new directory outside the installed skill. Use absolute paths; replace example paths with actual files:

```sh
python /path/to/paper-factory/scripts/research_workspace.py repository --url https://github.com/owner/repository --paths README.md path/to/implementation.py path/to/relevant_test.py --output-dir /work/repo-article/source-snapshot
```

Add `--ref BRANCH_OR_TAG` when needed. The helper clones without checkout and saves selected bytes under `sources/`, with the resolved commit and hashes in `repository.json`. Base the analysis on that revision. Capture success is not reading or execution evidence. Record access failures instead of inventing a snapshot.

## 2. Choose the contribution and venue

In one `venue-selection.md`, compare **three** of the five supported venues: `ieee-software`, `ieee-security-privacy`, `ieee-access`, `jors`, `joss`. Record article type, reader, actual evidence fit, missing eligibility/results, current-guidance status and choice. Distinguish practitioner lessons, a software artifact and a research article with experiments. Keep poor or blocked candidates visible rather than pretending three are eligible. Recommend one with explicit conditions when evidence is insufficient.

Read current official author instructions and the original template. Keep one `guidance.md` with source URLs, check date, article type, template version/hash/licence, required structure, length, citation/figure rules, declarations and output format. Mark partial or blocked access honestly. Samsung CSE8 and Signal Processing/Communication & Networks are topic scope, not an approved journal list. Do not add venues for this workflow.

## 3. Write and check

Write one actual `paper.md` and a bibliography of verified relevant records. Use the selected article structure and fair primary-literature comparisons. Record missing experiments or novelty evidence rather than inventing results. Missing author facts belong in the checklist; never fill JOSS YAML with fictitious identities to pass validation.

Reuse the existing claim ledger and its literal source witnesses. The [input contracts](researcher-convenience.md) define bibliography, reading-card and evidence records; [tools.md](tools.md) describes output options.

```sh
python /path/to/paper-factory/scripts/import_references.py --input /work/repo-article/paper.bib --output-dir /work/repo-article/imported
python /path/to/paper-factory/scripts/research_workspace.py evidence --root /work/repo-article --ledger /work/repo-article/claims.json --output-dir /work/repo-article/evidence
python /path/to/paper-factory/scripts/export_manuscript.py preflight --manuscript /work/repo-article/paper.md --venue SELECTED_ID
python /path/to/paper-factory/scripts/export_manuscript.py export --manuscript /work/repo-article/paper.md --venue SELECTED_ID --output-dir /work/repo-article/exported
```

Run export only when prerequisites are available. Access/JORS require `--template ABSOLUTE_FILE` for preflight and export. JOSS uses genuine YAML metadata, `paper.bib` and referenced local figures; it does not render the publisher PDF. Bibliography import preserves supplied BibTeX/RIS/CSL-JSON metadata; it neither verifies publications nor converts RIS to JOSS BibTeX. Keep failures visible and deliver the incomplete source when rendering or author facts are unavailable.

## 4. Bundle and stop

Create one `bundle-plan.json` for `submission_support.py bundle`. Allowlist only the manuscript source (`manuscript`), bibliography (`bibliography`), selection (`venue_selection`), existing `evidence/evidence.json` (`evidence`), guidance (`guidance`), needed figures and requested exports. Paths are relative to the source root; do not copy the entire repository or unrelated logs.

Set `article_type`, `draft_status` (`draft` or `incomplete`), `guidance_status` (`verified`, `partial` or `blocked`) and explicit `missing_evidence`. Leave unsupplied declarations/confirmations pending. For JSON evidence, the bundle compares the saved manuscript hash and carries failed, empty, malformed or inconsistent claim results into the checklist. Original bytes survive even when the status becomes incomplete. Authored text notes are manual records, not machine-verified reports; changed source witnesses require the existing evidence/impact tools.

```sh
python /path/to/paper-factory/scripts/submission_support.py bundle --root /work/repo-article --plan /work/repo-article/bundle-plan.json --output-dir /work/repo-article-bundle
```

The output directory must be new and outside the source root. Inspect the actual files, manifest and checklist. Report commands/exit codes and separate completed file preparation from unverified rendering, scientific evidence and human approval. Exit 0 means a bundle was written, not that its evidence passed or it is submission-ready. Formatting or declarations cannot clear a draft's research gaps. Deliver the actual bundle and stop.
