# Document conversion reuse

Reviewed 2026-09-30 before adding PDF dependencies. The implementation delegates
format conversion, citation processing and PDF layout to maintained projects.

| Component | Primary source / license | Use |
| --- | --- | --- |
| Pandoc | [Manual](https://pandoc.org/MANUAL.html), [GPL-2.0-or-later](https://github.com/jgm/pandoc/blob/main/COPYING.md) | Existing external executable; converts Markdown and verified CSL JSON through citeproc to standalone LaTeX, DOCX and Typst. No converter source is copied. |
| Typst | [Project](https://github.com/typst/typst), [Apache-2.0](https://github.com/typst/typst/blob/main/LICENSE), [native line numbering](https://typst.app/docs/reference/model/par/#definitions-line) | Maintained typesetting engine, with sandbox root restricted to the compilation directory. Native page/line numbering and Pandoc metadata set the layout. No TeX distribution installation is required for PDF. |
| typst-py | [Binding](https://github.com/messense/typst-py), [Apache-2.0](https://github.com/messense/typst-py/blob/main/LICENSE) | Optional PDF extra. Installed `typst` 0.15.0 embeds the engine and compiles Pandoc-generated Typst. |
| pypdf | [Project](https://github.com/py-pdf/pypdf), [BSD-3-Clause](https://github.com/py-pdf/pypdf/blob/main/LICENSE) | Optional PDF extra, installed 6.19.0. Reopens PDFs to check pages and inspect text/metadata for identity leakage in anonymous-review manuscripts. |
| python-docx | [Documentation](https://python-docx.readthedocs.io/en/latest/), [MIT](https://github.com/python-openxml/python-docx/blob/master/LICENSE) | Optional PDF/package extra, installed 1.2.0. Applies native Word continuous line-number settings and page-number fields to Pandoc exports; independently reopens the result. |
| lxml | [Upstream licensing](https://lxml.de/licence.html), BSD-3-Clause | Existing python-docx dependency, installed 6.1.3. Shipped licenses record BSD-3-Clause core and PSF/ElementTree exceptions; binary dependencies retain zlib, LGPL-2.1 iconv and MIT libxml2/libxslt notices. The application uses only core XML support, not optional isoschematron resources or test scripts. No XML parser source or binary is vendored. |
| CSL styles | [Citation Style Language project](https://citationstyles.org/), [maintained repository](https://github.com/citation-style-language/styles), [CC-BY-SA-3.0 and attribution](https://github.com/citation-style-language/styles#licensing) | Pandoc accepts an author-supplied local CSL file. Record its source and license in compiler settings; the copied style is hashed and its author/contributor metadata is preserved. An officially prescribed style cannot silently become Pandoc's default. No styles are vendored. |
| Poppler | [Official project](https://poppler.freedesktop.org/), GPL-2.0-or-later | Development visual verification with the existing bundled `pdftoppm`; no runtime dependency or rendering engine is implemented in this repository. |

The `conversion` module is a small subprocess/binding adapter. The Phase 1 draft
path retains standalone TeX or `COMPILE_READY` when Pandoc is absent; requested
PDF compilation uses this same maintained backend. Phase 2 requires actual PDF,
LaTeX and DOCX exports, not an unverified compile command. Install `.[pdf]` and
provide an existing Pandoc executable. LaTeX exports contain native `lineno`
instructions when required; compiling those sources separately requires the
normal publisher/TeX environment. PDF output uses Typst independently. Missing tools and failed exports preserve
the canonical source, produce a failure record and prevent readiness.

Venue compilation supports verified **free initial submission** requirements.
Exact publisher class/template requirements and unsupported required supplements
remain explicit blockers. Scientific prose, measured claims and bibliography are
derived from the approved freeze, while author declarations and scope-fit/cover
letter text must be supplied by the author. Citation existence and numerical
consistency checks do not assess scientific merit or prove a scope-fit statement.

Anonymous-review output omits author metadata and deterministic internal audit
details, redacts known identity tokens, and checks generated PDF metadata/text.
Bibliographic self-identification is reported for author review, rather than
inventing modified citation metadata. This is a conservative aid: it cannot
recognize every identifying phrase. Author metadata, policy captures and audit
supplements stay administrative; the whole ZIP is not a blinded-review document.
