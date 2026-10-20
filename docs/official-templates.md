# Official magazine manuscript templates

IEEE Software and IEEE Security & Privacy exports now use the Word files returned by the publisher's [IEEE Template Selector](https://template-selector.ieee.org/), verified on 18 October 2026. These are magazine templates, not conference templates. The [IEEE magazine author guidance](https://magazines.ieeeauthorcenter.ieee.org/create-your-ieee-magazine-article/authoring-tools-and-templates/ieee-article-templates/) explains that final magazine formatting is applied after acceptance.

| Venue | Selector article category | Official Word file | Template association |
|---|---|---|---|
| IEEE Software | Original Research | CS_Mag_7_22.docx | 549 |
| IEEE Security & Privacy | Original research and Brief | CS-Mag-template.docx | 405 |

The exact original bytes, source URLs, retrieval date, publisher modification timestamp, size and SHA-256 are retained in `src/paper_factory/templates/provenance.json`. Conversion verifies the bytes before using them as Pandoc's reference document. Runtime packaging copies and inventories these assets; ordinary exports do not download templates or require an account.

Parsed manuscript content is mapped to the actual publisher styles for title, authors, abstract, body, headings, references and captions. The publisher's one-column front matter and two-column body sections are retained. Tables span the printable width. Publisher examples, placeholder editors, sample copyright and artwork are excluded. The conversion receipt lists these adaptations. Source Markdown remains unchanged. Official font names remain in Word; locally unavailable proprietary Helvetica-Light and Cheltenham-Book fonts are substituted by Microsoft Word. The renderer reports missing template fonts, and exact proprietary font fidelity is not attested.

The PDF is rendered from the exact exported Word file through an independent, hidden Microsoft Word instance, opened read-only with macros disabled. Its receipt binds the source Word SHA. This native PDF path currently requires **Windows and installed Microsoft Word**. Failure leaves the official Word document available and reports an error; it does not silently produce a generic Typst PDF. Other non-venue conversion uses retain the existing bundled converter behavior.

Using the official template does not establish complete editorial compliance or publication merit. Word budgets, abstract length, reference style and completeness, author material, every-page visual inspection, contribution and evidence remain separate checks. Template changes require acquiring and inspecting the publisher's new bytes and updating provenance, rather than editing the retained official files.

Publisher-specific native citation typography is applied separately: Software uses superscript numbers outside punctuation; S&P uses bracketed callouts inside terminal punctuation. Reference labels use a following period, publisher hanging indents and readable left-aligned URL wrapping. Scientific Markdown, quoted source content and exact hyperlink targets are retained. Unknown bibliographic authors or titles are not invented; completeness and final reference editing remain separate from typography.

## Preflight of the exact article and exported files

The [focused four-request continuation](manuscript-improvement.md) reserves source selection, completed analytical results, both magazine drafts, and independent assessment in that order. A single writer response contains the two alternatives. It does not execute Frontron. Each new candidate must pass its own source/quotation admission and publisher-template preflight before becoming an independent-review target. The original eight reservations and the one authorized four-request extension remain a single native budget of at most twelve; template conversion, native measurement and deterministic classification repair add no model requests.

Preflight first applies `validate_manuscript` to the canonical article with its retained author block. It checks abstract structure and length, reference numbering and retained metadata, keywords, AI disclosure, unfinished tokens, and Software's actionable insights. Markdown word counts are estimates. The current numerical rules and counting scopes are documented separately in [journal-compliance.md](journal-compliance.md); older sample limits printed in a publisher template do not override the retained current guidance.

The native checks then use the actual files:

- Microsoft Word measures the saved official Word document, including the abstract, references, visual counts and venue-specific effective word count. Its styles, sections, columns, callouts and bibliography conventions are inspected separately from those counts.
- Conversion receipts must match the exact Markdown, original publisher template and output hashes. The PDF receipt must also identify the exact saved Word file used to render it.
- Every actual PDF page is rendered to a retained PNG. Page hashes, text hashes, invalid or blank text, and characters beyond page bounds are checked. Automatic structure checks do not establish that every layout or figure looks correct; direct visual review remains a separate pending requirement.

The focused state's `format_preflight[venue].report` is a wrapper containing the editorial preparation, pure report, outputs, conversion receipts, errors and, when native conversion proceeds, the full `compliance` report. The UI displays that full report, or the pure report if conversion has not reached native inspection, and shows conversion errors separately. `content_format_passed` requires every manuscript and native check to pass. It does not imply scientific merit, verified author facts, author consent, or actual submission.

## Preserved responses, repaired classification and human preparation

Two narrow repairs can reuse an already completed model response: separating exact retained primary-document witnesses from repository evidence, and changing exact retained primary-paper citation kinds from literature tokens to document tokens. Both retain the original response, rejection, error and counters, and append normalization proofs with original/result hashes. Scientific claims and literal quotations are preserved. The normalized candidate must still pass the original strict source checks and actual Word/PDF preflight. A matching-ID, matching-hash or literal-quotation failure is not excused, and no new writer request or budget grant is created by a repair. If a repair or native check fails, its reason remains visible and no submission-ready status is inferred.

The final submission stage binds the chosen manuscript, independent assessment, actual author metadata and official outputs. The author must supply missing biography facts, relevant keywords, actual funding/conflict statements and any required photograph. Six biography details—role, location, research interests, highest completed degree, degree institution and professional membership—start as explicit manual inputs; truthful None/N/A entries are allowed where applicable. Public ORCID data does not supply consent or unlisted credentials.

These supplied supplements produce a new official Word/PDF pair and a new bound compliance report. Previous page review and author approval are not copied to the new files. The author must review every new page and confirm actual identity, all-author approval, originality, rights, AI disclosure and current venue instructions before a submission ZIP is assembled. Actual portal submission and a real manuscript ID remain a separate human action. Neither official formatting, a passed native preflight nor model scores guarantee nine-point ratings or publication.
