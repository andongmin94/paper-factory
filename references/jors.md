# Journal of Open Research Software — Software Metapaper

Choose `jors` for reusable research software whose code, quality control, availability, and reuse can be documented. This route supports Software Metapapers, not the separate “Issues in Research Software” article category. Do not apply that category's 3,000–4,000-word guidance to metapapers.

## Official sources — checked 2026-11-02

- [Submission guidelines and template links](https://openresearchsoftware.metajnl.com/about/submissions)
- [Official Word template, version 0.2](https://account.openresearchsoftware.metajnl.com/index.php/up-j-jors/libraryFiles/downloadPublic/4)

The original DOCX was downloaded and read directly; SHA-256: `e7d18e25a580011a4b06fb42675dec01154d1101759e7fdddeffec392205d0f8`. Supply this original via `--template ABSOLUTE_FILE` for both preflight and export. The template is not bundled because a redistribution license was not established. Its article copyright notice is not a blanket license to redistribute the template.

## Required structure and bibliography

Preserve the template's three main sections:

1. **Overview:** factual software title, authors and roles/affiliations, abstract, keywords, introduction with alternatives, implementation and architecture, quality control.
2. **Availability:** operating system, programming language, system requirements, dependencies, repository/archive location, open license, version, dates, persistent archive identifier, and supporting-file language.
3. **Reuse potential:** realistic reuse cases, extension and support arrangements.

Include competing interests, references, and applicable acknowledgments/funding. The template suggests an abstract of about 100 words; this is a target, not a strict cap. No metapaper-wide word/reference ceiling was established. Biographies are not required.

Current guidelines require Vancouver references in first-citation order, with normal-text parenthetical citations such as `(1, 2)` inside terminal punctuation. They supersede the older template's conflicting Harvard/bracketed instructions. The adapter uses the current citation convention; authors must supply accurate Vancouver bibliography entries and available DOI/URLs.

## Output and remaining preparation

Use the standard Markdown → verified DOCX → native Word PDF path in [tools.md](tools.md). Include tables as actual tables. Retain figure titles, captions, separate alt text and source permissions; submission requires separate figure files, no more than 20 MB each. The official checklist sets 150 dpi minimum and prefers 300 dpi, while the main figure guidelines require at least 300 dpi. Prepare figures at 300 dpi or higher; this resolution requirement is not automatically verified by the adapter.

Public software, its archive identifier, author consent, competing interests, cover letter, proposed reviewers, and applicable fees remain submission preparation. DOCX structure checks do not establish native Word/PDF rendering or completed visual inspection.
