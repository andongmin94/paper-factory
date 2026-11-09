# Standalone research and document tools

Resolve this skill's directory from the loaded `SKILL.md`. Scripts find their assets relative to their own location, so the installed package can be copied to another directory. Keep user research and output outside the installed skill.

## Runtime and source work

Use ordinary agent search, repository, browser, and file tools for actual research and writing. Retain the inspected revision and original source/document bytes. Do not execute the input project unless authorized. No special research-response schema wraps the article; canonical authored Markdown is sufficient.

Use the managed Python and libraries when available. The tools require Python 3.11 or later and the dependencies declared by the package. Word output uses an existing Pandoc executable and installed Microsoft Word on Windows for native PDF generation and measurement. JOSS source checks use Pandoc and the existing bibliography parser without Word. Inspect actual dependencies before installing anything; a missing component is a reported preparation issue.

Run the installed scripts' `--help` before using unfamiliar options. Replace `$python`, `$skillDirectory`, `$manuscript`, and `$newOutputDirectory` below with the actual resolved executable and absolute paths. Do not use common system environment names for task variables.

## Manuscript preflight and official export

`scripts/export_manuscript.py` accepts a completed Markdown manuscript. It performs deterministic preparation and export without generating scientific prose.

```powershell
& $python "$skillDirectory/scripts/export_manuscript.py" preflight --manuscript $manuscript --venue ieee-software
& $python "$skillDirectory/scripts/export_manuscript.py" export --manuscript $manuscript --venue ieee-software --output-dir $newOutputDirectory
```

| Venue identifier | Template/input | Export |
| --- | --- | --- |
| `ieee-software`, `ieee-security-privacy` | Retained official DOCX | DOCX and native Word PDF |
| `ieee-access`, `jors` | Official DOCX supplied with `--template ABSOLUTE_FILE` | DOCX and native Word PDF |
| `joss` | Authored YAML Markdown, `paper.bib`, local figures | Submission source package |

For Access and JORS, download the original linked by [Access guidance](ieee-access.md) or [JORS guidance](jors.md), and supply its absolute path to both commands. The exact file must match the recorded publisher SHA-256; the tools do not fetch a template or accept a generic substitute.

```powershell
& $python "$skillDirectory/scripts/export_manuscript.py" preflight --manuscript $manuscript --venue ieee-access --template $officialTemplate
& $python "$skillDirectory/scripts/export_manuscript.py" export --manuscript $manuscript --venue jors --template $officialTemplate --output-dir $newOutputDirectory
```

Use the corresponding venue's template for each command. Word `preflight` reads the manuscript and checks the template without launching Word. Word `export` requires a new output directory, retains exact Markdown bytes, produces DOCX, renders that exact saved DOCX through hidden read-only Word to PDF, measures native counts, and retains conversion/format/provenance reports and all-page PNGs. A failed export retains its directory for diagnosis; do not overwrite it or reuse an earlier export as a successful result.

Word export also retains the local relative images recognized by the converter's Markdown reader, including reference-style images. The source root is the manuscript directory, or the one existing absolute `--resource-dir` when supplied. Referenced files are copied byte for byte to the same relative paths beside the retained `manuscript.md`, and the converter reads those copies. The manifest records their hashes; original files and Markdown bytes remain unchanged. Missing files, symlinks, absolute or escaping paths, external image URLs, Windows-incompatible filenames, case-insensitive file/directory collisions and collisions with generated output paths are rejected.

Keep the whole export directory to re-export its retained manuscript after moving it, using the same converter and required official template. This retains the Markdown image inputs; it does not collect raw HTML/TeX assets or redistribute templates, Pandoc, Word or fonts. Those rendering prerequisites remain separate. A later submission bundle still copies only its explicitly selected files, including each intended figure.

Conversion warnings stop the export, including Pandoc replacing a missing figure with its description. Embedded common raster images are checked for readable image structure before delivery. Read the reported diagnostic and repair the actual input in a new revision; a retained partial DOCX is a failed output. These checks do not establish visual fidelity or validate every vector format; inspect all final pages as described below.

Body figures are reduced proportionally when needed to fit the publisher's column width and printable page height; smaller figures are not enlarged. This preserves image bytes but cannot ensure that labels remain readable after reduction. Inspect their actual final size during page review.

For Word venues, optional `--profile ABSOLUTE_FILE` uses the multi-author profile from `submission_support.py authors`, including its generated `authors.json`. Preparation and export report missing author facts, checking identity fields within that author's own byline block and order. Access requires biographies; JORS does not. The manuscript must already carry the intended author blocks; export does not insert them from metadata. Field presence is not proof of factual accuracy or consent. Optional `--pandoc ABSOLUTE_EXECUTABLE` selects an existing Pandoc binary; otherwise the helper resolves an available installation. Diagnostics and conversion verify the actual Pandoc identity. Do not silently replace the publisher-template export with a generic alternative if Word, Pandoc, or required assets are unavailable.

Exit status distinguishes passed content-format checks, a completed report with failed checks, and input/conversion errors; inspect both `--help` and the actual result. A passing format report is not scientific approval. `submission_ready: false` can remain while author information, declarations, page approval, or current guidance checks are pending.

## JOSS source export

Read [JOSS guidance](joss.md) before preparing the canonical `paper.md`. Set `bibliography: paper.bib` in its YAML, use the required sections and Pandoc citations such as `[@key]`, and supply actual author metadata in YAML. `--profile` and `--template` are unsupported for JOSS.

```powershell
& $python "$skillDirectory/scripts/export_manuscript.py" preflight --manuscript $manuscript --venue joss
& $python "$skillDirectory/scripts/export_manuscript.py" export --manuscript $manuscript --venue joss --bibliography $bibliography --output-dir $newOutputDirectory
```

The bibliography defaults to sibling `paper.bib`; `--bibliography ABSOLUTE_FILE` selects a supplied BibTeX file to preserve as `paper.bib`. Use `--resource-dir ABSOLUTE_DIRECTORY` when local image paths resolve relative to another retained source directory. The tools inspect Pandoc metadata, sections, citation keys, bibliography records, and local media, then preserve `paper.md`, `paper.bib`, and referenced figures with hashes in the new output directory. Existing BibTeX/RIS/CSL-JSON import remains a separate metadata tool; RIS is not a JOSS submission bibliography.

This path does not generate DOCX, call Inara, upload sources, or produce a PDF. Report the completed source checks separately from unperformed rendering and visual inspection. For a JOSS submission bundle, select manuscript and bibliography roles plus the referenced figure files. `finalize_submission.py` applies to native Word reports and rejects JOSS; do not create a synthetic Word/PDF report for a source package.

## Public ORCID facts

Use `scripts/lookup_orcid.py --help` for its current CLI, then provide an ORCID identifier or accepted public profile URL. The helper requests public ORCID records and normalizes available names, affiliations, emails, and biography material. It does not access private account data or establish author consent. Preserve returned provenance and missing fields; do not infer an email, current role, degree, or approval from absence. Multiple public affiliations or contacts need the actual author's selection for the paper.

## Research and submission files

Use [researcher-convenience.md](researcher-convenience.md) for the optional environment diagnostic, status/continuation snapshots, literature reading cards, evidence links, comparisons, editorial reports, coauthor/anonymous drafts, reviewer responses and submission bundles. Each writes to a new output directory or reads a saved checkpoint; no scientific writing or review runs implicitly. Reuse a private author profile only when selected for that paper.

The same reference describes `research_workspace.py impact` for revisiting only changed or explicitly selected evidence and `finalize_submission.py check` for reconciling existing exact-file format, visual, scientific and genuine human records for Word exports. Final checking leaves old reports intact and is separate from uploading or acceptance. Apply the selected venue's policy before preparing responses; JOSS does not permit AI-written author–editor/reviewer conversations except translation.

## Exact-file verification

Retained templates and acquisition metadata are in `assets/templates/`; Access and JORS originals are supplied externally because their redistribution license was not established. Verify the selected asset hash against its provenance. JOSS includes the MIT-licensed Inara source example with its license notice. A template proves the bytes used, not current rules, exact proprietary font availability, or acceptance.

After export, inspect every PNG of the exact final PDF at readable original size. Check source-derived title and author layout, column order, technical notation, table captions/continuations, references, glyphs, clipping, page furniture, and final-page balance. Native bounds and glyph checks cannot replace visual inspection. Record the actual PDF and ordered page-image hashes, reviewer, and limitations separately from human author approval.

When correcting layout or a local factual issue, keep the earlier output and review binding. Re-render and inspect all pages of the new output; do not claim that an older review covers changed bytes. Deliver content recommendation, measured format results, page observations, missing human items, and actual submission status as separate facts.
