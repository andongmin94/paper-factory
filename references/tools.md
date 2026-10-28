# Standalone research and document tools

Resolve this skill's directory from the loaded `SKILL.md`. Scripts find their assets relative to their own location, so the installed package can be copied to another directory. Keep user research and output outside the installed skill.

## Runtime and source work

Use ordinary agent search, repository, browser, and file tools for actual research and writing. Retain the inspected revision and original source/document bytes. Do not execute the input project unless authorized. No special research-response schema wraps the article; canonical authored Markdown is sufficient.

For Codex document work, use `mcp__codex_app__load_workspace_dependencies` to locate its managed Python and libraries. The export tool requires Python 3.11 or later and the document dependencies declared by the package, an existing Pandoc executable, and installed Microsoft Word on Windows for native PDF generation and measurement. It does not distribute a private Python or Word installation. Inspect actual dependencies before installing anything; a missing component is a reported preparation issue.

Run the installed scripts' `--help` before using unfamiliar options. Replace `$python`, `$skillDirectory`, `$manuscript`, and `$newOutputDirectory` below with the actual resolved executable and absolute paths. Do not use common system environment names for task variables.

## Manuscript preflight and official export

`scripts/export_manuscript.py` accepts a completed Markdown manuscript and an optional explicit multi-author profile. It performs deterministic preparation and export without generating scientific prose.

```powershell
& $python "$skillDirectory/scripts/export_manuscript.py" preflight --manuscript $manuscript --venue ieee-software
& $python "$skillDirectory/scripts/export_manuscript.py" export --manuscript $manuscript --venue ieee-software --output-dir $newOutputDirectory
```

Supported venue identifiers are `ieee-software` and `ieee-security-privacy`. `preflight` reads the manuscript and retained template without launching Word. `export` requires a new output directory, retains exact Markdown bytes, verifies the official template, produces DOCX, renders that exact saved DOCX through hidden read-only Word to PDF, measures native counts, and retains conversion/format/provenance reports and all-page PNGs. A failed export retains its directory for diagnosis; do not overwrite it or reuse an earlier export as a successful result.

Optional `--profile ABSOLUTE_FILE` uses the same multi-author profile as `submission_support.py authors`, including its generated `authors.json`. Preparation and export report every author's missing facts and biography details, checking identity fields within that author's own byline block and order. The manuscript must already carry the intended author blocks; export does not insert them from metadata. Field presence is not proof of factual accuracy or consent. Optional `--pandoc ABSOLUTE_EXECUTABLE` selects an existing Pandoc binary; otherwise the helper resolves an available installation. Diagnostics and conversion verify the actual Pandoc identity rather than accepting any successful version command. Do not silently replace the publisher-template export with a generic alternative if Word, Pandoc, or required assets are unavailable.

Exit status distinguishes passed content-format checks, a completed report with failed checks, and input/conversion errors; inspect both `--help` and the actual result. A passing format report is not scientific approval. `submission_ready: false` can remain while author information, declarations, page approval, or current guidance checks are pending.

## Public ORCID facts

Use `scripts/lookup_orcid.py --help` for its current CLI, then provide an ORCID identifier or accepted public profile URL. The helper requests public ORCID records and normalizes available names, affiliations, emails, and biography material. It does not access private account data or establish author consent. Preserve returned provenance and missing fields; do not infer an email, current role, degree, or approval from absence. Multiple public affiliations or contacts need the actual author's selection for the paper.

## Research and submission files

Use [researcher-convenience.md](researcher-convenience.md) for the optional environment diagnostic, status/continuation snapshots, literature reading cards, evidence links, comparisons, editorial reports, coauthor/anonymous drafts, reviewer responses and submission bundles. Each writes to a new output directory or reads a saved checkpoint; no scientific writing or review runs implicitly. Reuse a private author profile only when selected for that paper.

The same reference describes `research_workspace.py impact` for revisiting only changed or explicitly selected evidence and `finalize_submission.py check` for reconciling existing exact-file format, visual, scientific and genuine human records. Final checking leaves old reports intact and is separate from uploading or acceptance.

## Exact-file verification

The original official DOCX files and their acquisition metadata are in `assets/templates/`. Verify the selected asset hash against its provenance. A retained publisher template proves the bytes used, not current rules, exact proprietary font availability, or acceptance.

After export, inspect every PNG of the exact final PDF at readable original size. Check source-derived title and author layout, column order, technical notation, table captions/continuations, references, glyphs, clipping, page furniture, and final-page balance. Native bounds and glyph checks cannot replace visual inspection. Record the actual PDF and ordered page-image hashes, reviewer, and limitations separately from human author approval.

When correcting layout or a local factual issue, keep the earlier output and review binding. Re-render and inspect all pages of the new output; do not claim that an older review covers changed bytes. Deliver content recommendation, measured format results, page observations, missing human items, and actual submission status as separate facts.
