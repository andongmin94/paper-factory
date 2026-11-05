# From a repository URL to one draft bundle

Use this procedure when the user supplies a GitHub repository URL and requests a paper draft. Lead the reading, reasoning and writing in the current conversation. Use the existing file tools for collection and preparation; they do not select a contribution or author a manuscript. Keep the current five supported venues and complete one case without an automatic improvement loop.

## 1. Read and preserve the relevant sources

Confirm the requested repository, ref and execution scope. Inspect its actual tracked tree with read-only repository tools before selecting paths. Read the README, consequential implementation, relevant tests and any retained experiments or results; do not classify the project from filenames or repeat unverified README claims as observations. Follow relevant local instructions. Do not modify the user's repository or execute its code, build or tests without authorization.

Use a new research directory outside the installed skill. Replace the example paths with files found in the actual tree:

```sh
python /path/to/paper-factory/scripts/research_workspace.py repository --url https://github.com/owner/repository --paths README.md path/to/implementation.py path/to/relevant_test.py --output-dir /work/repo-article/source-snapshot
```

Add `--ref BRANCH_OR_TAG` when needed. The helper clones without checkout, preserves selected original tracked files under `sources/`, and records the repository URL, resolved commit and file hashes in `repository.json`. Read the captured originals and base claims on that resolved revision. A successful collection proves acquisition, not that the files were read or that the software works. Record unavailable files or restricted access explicitly.

Reuse the existing evidence ledger. Use `source_declared` for project claims, `observed_static` for inspected behavior, `measured` only for retained real measurements, and `derived` or `proposed` for inference or proposals. Keep unverified claims and needed observations in the missing-evidence record. Read relevant primary literature bodies and retain their actual reading scope using the existing [reading-card and evidence tools](researcher-convenience.md).

## 2. Compare exactly three candidates and recommend one conditionally

Choose three from `ieee-software`, `ieee-security-privacy`, `ieee-access`, `jors` and `joss`; do not add venues. Use the [contribution-selection comparison](contribution-selection.md) to record intended reader, article type, evidence fit, missing eligibility/evidence, official-guidance status and the decision in one short `venue-selection.md`. Include a rejected or blocked candidate honestly if fewer than three have a plausible fit. Recommend one and explain the conditions; this does not establish eligibility or acceptance.

Prioritize supported contribution and evidence over impact factor. Treat user-supplied scope labels such as Samsung CSE8 or SP/C&N as topic cues, not an accredited or approved journal list. General authoring assistance does not by itself establish that software qualifies for JORS or JOSS. Check the selected article type against current official rules and actual project evidence.

Read the existing venue reference, current official author guidelines and official template source directly. Keep one short `guidance.md` with URLs, check date, article type, required options/limits, template provenance and licenses, actual reading/access status, and remaining AI/ethics/availability checks. Reuse retained source records rather than duplicating journal policies here. Mark inaccessible or partly read instructions `blocked` or `partial`; a remembered rule, search snippet or old template does not make them verified.

## 3. Write one actual draft and bibliography

Write the supported contribution as an English manuscript using the selected category's structure. Use actual source witnesses and fair comparisons; exclude invented performance, adoption, novelty and human approvals. If the available evidence cannot complete the argument, write the supported sections as prose, retain the source and mark the draft incomplete. Do not stop at an outline or selection table, or expand the scope to manufacture a complete result.

Preserve canonical `paper.md` and a bibliography containing only verified, actually relevant records. Keep missing author information in the checklist. In particular, do not fill JOSS YAML with fictitious authors or affiliations: retain an incomplete source draft and deliver it through the draft bundle until genuine metadata is supplied. The syntax example is not evidence about the user's software. Keep actual AI-use facts and missing human verification distinct, following the current venue policy.

## 4. Connect the existing preparation tools

Use absolute paths and new output directories. The following commands illustrate the existing contracts; replace `SELECTED_ID` with the chosen supported venue. Consult [tools.md](tools.md) and [researcher-convenience.md](researcher-convenience.md) for the current options and input records.

```sh
python /path/to/paper-factory/scripts/import_references.py --input /work/repo-article/paper.bib --output-dir /work/repo-article/imported
python /path/to/paper-factory/scripts/research_workspace.py evidence --root /work/repo-article --ledger /work/repo-article/claims.json --output-dir /work/repo-article/evidence
python /path/to/paper-factory/scripts/export_manuscript.py preflight --manuscript /work/repo-article/paper.md --venue SELECTED_ID
python /path/to/paper-factory/scripts/export_manuscript.py export --manuscript /work/repo-article/paper.md --venue SELECTED_ID --output-dir /work/repo-article/exported
```

Bibliography import accepts existing BibTeX/RIS/CSL-JSON; it does not verify identity, read papers or convert RIS into a JOSS submission bibliography. Inspect its findings and preserve the original bibliography. Reuse one claim ledger and its generated evidence report instead of creating a second evidence system.

For Access/JORS, supply the verified original `--template ABSOLUTE_FILE` to both preflight and export. For JOSS, use actual YAML metadata, `paper.bib` and referenced local figures; apply `--bibliography` or `--resource-dir` only as documented. Keep preflight failures and missing data visible. Do not insert false values to pass a check or repeatedly rerun an unchanged passing check.

Run the existing export only when its prerequisites are available. A missing Word/PDF environment leaves native rendering and page inspection unverified; preserve the source draft and preparation findings. JOSS source export does not run Inara or validate PDF layout. A format check cannot establish the contribution, software eligibility or human approval. Do not fabricate output or substitute a generic renderer as a verified official export.

## 5. Bundle the minimum and finish

Prepare one plan for the existing `submission_support.py bundle`. Select the preserved source as `manuscript`, the actual bibliography as `bibliography`, and one short record each as `venue_selection`, `evidence` and `guidance`; add only needed `figure` files and any actual requested export. Paths are relative to the explicit source root. Do not bundle the entire repository or unrelated logs.

Select the existing `research_workspace.py evidence` JSON report (for example, `evidence/evidence.json`) with role `evidence`. For `.json` evidence selections, the bundle checks the saved `manuscript_sha256` against the single selected manuscript and carries failed, empty, malformed or inconsistent claim results into `missing_evidence` and the checklist. It preserves the original report and files even when the draft becomes `incomplete`; exit 0 means the bundle was written, not that its evidence passed. These are saved-report checks only, not a new source inspection, scientific judgment or author approval. Rerun the existing evidence/impact tools when source witnesses change. Authored Markdown/text evidence notes remain manual records and are not machine-verified binding reports.

Set the optional `draft_status` to `draft` or `incomplete`, `article_type` to the selected category, `guidance_status` to `verified`, `partial` or `blocked`, and `missing_evidence` to the unresolved facts. These are preparation statements, not proof of compliance. Incomplete drafting, unverified guidance and missing evidence remain conditional. Leave unsupplied declarations and author confirmations pending.

```sh
python /path/to/paper-factory/scripts/submission_support.py bundle --root /work/repo-article --plan /work/repo-article/bundle-plan.json --output-dir /work/repo-article-bundle
```

The new bundle directory must be outside its source root. Inspect its generated checklist and report the recommendation, actual draft/source files, bibliography, source revision, performed checks, unverified rendering and remaining human/evidence items. A draft bundle can be delivered after incomplete preflight or unavailable export; it is not submission-ready. The final-preparation tool cannot clear an existing draft or its evidence gaps through format checks or author confirmations; prepare a new final bundle only after actually resolving them. Preserve the source regardless of native output availability. Stop after this one case and its minimum bundle; further drafting, review, new venue support or submission needs the corresponding user request.
