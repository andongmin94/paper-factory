# IEEE Access research article

Choose `ieee-access` for completed engineering research with a supported method and result. Repository inspection alone does not establish experimental performance. This adapter covers the research-article route; do not infer that a project is suitable merely because it can be formatted.

## Official sources — checked 2026-11-02

- [Submission guidelines](https://ieeeaccess.ieee.org/authors/submission-guidelines/)
- [Preparing your article](https://ieeeaccess.ieee.org/authors/preparing-your-article/)
- [Official Word template](https://ieeeaccess.ieee.org/wp-content/uploads/2025/08/Access-Template-2024.docx)

The template was downloaded and read directly. Its SHA-256 is `c30433ce4e817bf4fba6dc69e6e4d5bf7fc1f8e7b0126374c65926dbd5d5b1bb`. Download this original and supply its absolute path with `--template` to both preflight and export. No template binary is redistributed: availability for manuscript preparation does not establish a general redistribution license. Preserve the publisher's rights and notices.

## Preparation and output

| Requirement | Scope |
| --- | --- |
| Format | Required Access template; double column, single spaced |
| Abstract | 150–250 words; one self-contained paragraph, without references, footnotes or displayed mathematics |
| Index terms | 3–10 manuscript keywords; template requests alphabetical, comma-separated terms |
| References | IEEE numbered bibliography with bracketed in-text citations |
| Authors | All authors on source and PDF; biographies below references; submitting author's ORCID required |
| Submission files | Matching Word/LaTeX source and PDF; no file over 40 MB |
| Length | No fixed page limit; under 20 pages recommended, with editorial scrutiny for longer papers |

Use the existing authored Markdown path described in [tools.md](tools.md), with canonical input `Keywords: term; term; term`. The Access mapper sorts these terms and outputs a comma-separated `INDEX TERMS` paragraph in Word. Supply accurate complete references. Do not impose Software's 4,200-word/15-reference limits or its actionable-insight block.

Disclose actual AI-generated text and the system used in accordance with the current acknowledgments/citation policy. Obtain genuine author approval and biographies; a profile lookup cannot supply consent. Keep journal fees and submission choices as human decisions.

Pandoc applies the verified reference DOCX, then native Windows Word produces and measures the exact PDF. DOCX/OOXML checks alone do not verify Word rendering, pagination, fonts, or every final page; leave those checks pending when Word is unavailable.
