# Journal preparation checks

Checked against current primary guidance on 18 October 2026. These are **Feature Article** preparation rules; a special issue must be selected separately. The older official Word files supply layout and citation conventions. Current venue instructions override their older sample word limits.

| Requirement | IEEE Software | IEEE Security & Privacy | App enforcement |
|---|---|---|---|
| Length | At most 4,200 effective words; references and biographies excluded; 250 per visual | 4,900–7,200 whole-article words, including table text and author material, plus 250 per visual | Hidden, read-only Microsoft Word statistics; Markdown estimate is a prefilter |
| Abstract | At most 150 words | At most 50 words | Native Abstract-style count, excluding the label and separate keyword paragraph; one paragraph without citations |
| References | At most 15 | At most 15 | Sequential source labels, descriptive retained metadata, native numbered-period bibliography |
| Practical takeaways | Three actionable-insight bullets | No equivalent numeric requirement verified | Software requires exactly three bullets |
| Native callouts | Superscript outside punctuation | Bracketed inside punctuation, as its acquired submission template instructs | Word-only typography; scientific Markdown remains unchanged |
| Keywords | Relevant keywords | Relevant keywords included in the whole-article count | Three to eight distinct terms is app policy; the upper limit is not a publisher rule |
| Author material | Actual identity, biography and author photograph | Actual identity and biography | Missing facts stay pending; public ORCID records never establish consent |
| Final checks | Actual author declarations and page review | Actual author declarations and page review | Author confirmation remains separate from automated checks and model scores |
| AI assistance | Disclose generated content | Disclose generated content | Acknowledgments must identify actual systems, use and affected manuscript parts; presence checking cannot verify an invented model name |

Numeric and Software-specific submission requirements come from the [IEEE Software call](https://www.computer.org/digital-library/magazines/so/cfp-ieee-software) and the current [S&P call repeating its general Author Information limits](https://www.computer.org/digital-library/magazines/sp/cfp-real-world-security-impact). Reading the latter does not select its special issue. The [Computer Society author guidance](https://www.computer.org/publications/author-resources) supplies keyword, biography, reference and author-responsibility guidance. Its complete final-material checklist applies after acceptance; the app distinguishes that preparation from initial-submission requirements. Publisher templates and their exact original hashes are documented in [official-templates.md](official-templates.md).

`journal_compliance.format_guidance` supplies the writer budget. `prepare_editorial_markdown` normalizes escaped prose separators, removes generated numeric self-attestation sentences, and fills bibliography metadata only from retained matching source records. It returns original/result hashes and each editorial change. Code escapes, scientific claims and author facts are preserved. Unknown reference metadata is never fabricated. Formatting does not certify reference accuracy or scientific novelty.

The [IEEE AI-content policy](https://open.ieee.org/author-guidelines-for-artificial-intelligence-ai-generated-text/) requires disclosure of generated content in Acknowledgments. The app uses retained tool/model provenance; it does not generate a statement claiming that the human author reviewed or approved the paper. Editing-only disclosure is recommended by IEEE; this app generates substantive manuscript content, so the disclosure check applies.

`validate_manuscript` is a pure prefilter. `compliance_report` measures the actual native Word file, verifies Markdown/template/Word/PDF receipts, and renders every actual PDF page with bundled PDFium and Pillow. Software's conservative count includes title/byline/abstract before References, replaces body table text with the visual allowance, and excludes biographies; S&P includes all Word text, including footnotes/endnotes and table text, plus its visual allowance. Final editorial counting can differ.

Every report item has `id`, `label`, `status` (`passed`, `failed`, `pending`), `stage`, `reason`, and `source_url`. `content_format_passed` requires all manuscript and native checks to pass before independent scientific review. `submission_ready` additionally requires actual human preparation. The submission stage records truthful identity, biography, photograph, originality, rights, funding/conflict, AI and approval facts; a nonempty biography alone cannot fill missing structured facts. Biography field checks prove supplied presence, not factual accuracy.

Whole-page PNG hashes, text hashes, character bounds and the exact source PDF hash are retained. Blank pages, invalid glyph text and characters beyond page bounds fail automatic checks. These checks do not detect every overlap, clipping defect or misleading figure. `visual_review` remains pending until an actual reviewer record identifies the exact PDF and all ordered page-image hashes. Source or export changes invalidate the binding. Locally unavailable proprietary template fonts are reported; Word substitutions do not attest exact font fidelity.

The Word/PDF/metrics operations require Windows and installed Microsoft Word, run hidden with macros disabled, and open only short exact read-only copies. The original documents and research counters are unchanged. No Docker, project execution, research restart or model call is part of journal compliance.
