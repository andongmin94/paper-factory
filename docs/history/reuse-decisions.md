> 역사 자료: Paper Factory 0.12.0 플러그인·호스트·수동 연구/투고의 기록입니다. 독립 앱의 현재 설치·사용 안내가 아닙니다. 기존 측정과 검증 주장을 새 앱의 성공으로 계산하지 않습니다.

# Reuse decisions

Reviewed 2026-09-30 before Phase 1 implementation. This is an implementation decision record, not a claim that any upstream system produces publishable science reliably. License names were checked against upstream license files or official service terms. Repository activity was checked through GitHub's repository and latest-commit APIs; a recent commit is evidence of activity, not a maintenance guarantee.

This is the original Phase 1 decision record. Phase 2 adoption of OpenAlex,
Beautiful Soup, citeproc, Typst, pypdf and python-docx supersedes the historical
deferrals below; see [Phase 2 reuse](phase2-reuse.md) and [conversion reuse](pdf-reuse.md).

## Adopt for Phase 1

| Component | License / primary source | Decision |
| --- | --- | --- |
| Python standard library | [PSF license](https://docs.python.org/3/license.html) | Use `subprocess`, `sqlite3`, `hashlib`, `json`, `csv`, `pathlib`, and `statistics`; avoid replacement libraries where these suffice. |
| Pydantic | [MIT](https://github.com/pydantic/pydantic/blob/main/LICENSE) | Validate persisted models and experiment manifests; reject invalid identifiers, unsupported claims, and impossible states. |
| Typer | [MIT](https://github.com/fastapi/typer/blob/master/LICENSE) | CLI command groups and parameter validation. |
| HTTPX | [BSD-3-Clause](https://github.com/encode/httpx/blob/master/LICENSE.md) | Bounded HTTP requests to scholarly metadata services; no separate metadata SDK is needed initially. |
| pytest | [MIT](https://github.com/pytest-dev/pytest/blob/main/LICENSE) | Development-only tests of actual integrity and execution boundaries. |
| SQLite | [Public domain](https://www.sqlite.org/copyright.html) | Use Python's bundled driver for transactional workspace state; no ORM or migration framework. |
| Git | [GPLv2 with upstream exceptions](https://github.com/git/git/blob/master/COPYING) | Invoke the installed executable for clone and revision identity; do not vendor Git or add GitPython. |
| Pandoc | [GPL-2.0-or-later](https://pandoc.org/MANUAL.html), [license](https://github.com/jgm/pandoc/blob/main/COPYING.md) | Optional installed executable for standalone LaTeX/PDF. CSL/citeproc styling is deferred to venue compilation. Do not recreate its parser or reference-style engine. |
| LaTeX | [LPPL 1.3c](https://www.latex-project.org/lppl/) for LaTeX itself | Optional installed PDF engine. A TeX distribution contains additional packages with their own licenses; Paper Factory does not redistribute that distribution. |

Only Pydantic, Typer, and HTTPX are direct application dependencies; pytest belongs in the development extra. Pandoc, Git, and TeX are external tools, not Python packages. With no PDF toolchain, preserve canonical Markdown, verified bibliography, and an explicit build recipe rather than report a fictitious PDF. Any installed distributions' transitive licenses remain part of their upstream distribution metadata; no upstream source is copied into this repository.

The Windows development environment was additionally checked through installed wheel `METADATA` and shipped license files on 2026-09-30. Direct versions: Pydantic 2.13.5, Typer 0.27.2, HTTPX 0.28.1, pytest 9.1.1. The resolved transitive packages are recorded here because a direct dependency's license does not cover its dependency tree:

| Installed transitive distributions | Verified licenses |
| --- | --- |
| pydantic-core 2.46.5, annotated-types 0.8.0, typing-inspection 0.4.4 | MIT |
| typing-extensions 4.16.0 | PSF-2.0 |
| annotated-doc 0.0.5, rich 15.0.0, markdown-it-py 4.2.0, mdurl 0.1.2 | MIT |
| shellingham 1.5.4 | ISC |
| colorama 0.4.6 | BSD-3-Clause |
| httpcore 1.0.9, idna 3.20 | BSD-3-Clause |
| anyio 4.15.1, h11 0.16.0 | MIT |
| certifi 2026.7.22 | MPL-2.0 |
| pluggy 1.6.0, iniconfig 2.3.0 | MIT |
| packaging 26.3 | Apache-2.0 OR BSD-2-Clause |
| Pygments 2.21.0 | BSD-2-Clause |

Typer 0.27.2's actual runtime requirements do not include a separately installed Click package. It bundles adapted Click 8.3.1 under `typer/_click`; its shipped `LICENSE.txt` is BSD-3-Clause, and its adapted `optparse` parser retains the PSF and Gregory Ward copyright attributions. These remain part of the Typer distribution; Paper Factory copies none of that code. The table reflects this environment rather than assuming an older dependency tree. Build backend setuptools is [MIT](https://github.com/pypa/setuptools/blob/main/LICENSE); pip is development-environment tooling, not an application runtime dependency. Other operating systems/Python versions may resolve additional conditional dependencies and should inspect those distribution licenses when installing.

`pypandoc_binary` 1.17 was installed only in the development environment to obtain an actual Pandoc executable for compiler smoke validation. The [pypandoc wrapper is MIT](https://github.com/JessicaTegner/pypandoc/blob/master/LICENSE); its bundled Pandoc retains Pandoc's GPL license. It is not declared as an application dependency and the application does not import it.

Latest observed default-branch commit dates (UTC): Pydantic 2026-09-29, Typer 2026-09-08, HTTPX 2026-02-23, pytest 2026-09-29, Pandoc 2026-09-29, Git 2026-09-28. All were non-archived at review time. These observations can be repeated with `https://api.github.com/repos/{owner}/{repo}/commits?per_page=1`.

## Autonomous research, experiments, literature, and writing

| Upstream | Verified license and activity | Phase 1 decision |
| --- | --- | --- |
| [AI Scientist](https://github.com/SakanaAI/AI-Scientist) and [v2](https://github.com/SakanaAI/AI-Scientist-v2) | [Custom AI Scientist Source Code License](https://github.com/SakanaAI/AI-Scientist/blob/main/LICENSE), December 2025; mandatory manuscript AI disclosure and use restrictions. Both heads 2025-12-19; non-archived. | Research references only. Do not import or copy their orchestration, prompts, or templates; they assume a broader autonomous LLM research loop than this slice needs. The current license must not be described as an ordinary permissive license. |
| [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory) | [MIT](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/main/LICENSE); head 2025-08-20, non-archived. | Its literature/experiment/report stages inform responsibility boundaries. No integration: broad agent and ML dependencies do not help execute a known reproducible manifest. |
| [AIDE](https://github.com/WecoAI/aideml) | [MIT](https://github.com/WecoAI/aideml/blob/main/LICENSE); head 2026-09-03, non-archived. | Defer optional experiment-generation assistance. Agentic code search is unnecessary for running user-defined commands and recording evidence; generated code would still require isolated execution and verification. |
| [PaperQA2](https://github.com/Future-House/paper-qa) | [Apache-2.0](https://github.com/Future-House/paper-qa/blob/main/LICENSE); head 2026-08-12, non-archived. | Potential later literature assistant only. Its PDF/text RAG and default LLM/embedding stack are not the research, evidence, or publication engine. |
| [GROBID](https://github.com/kermitt2/grobid) | [Apache-2.0 software; CC0 docs; CC-BY annotated data](https://grobid.readthedocs.io/en/latest/License/); head 2026-09-29, non-archived. | Defer PDF/reference extraction service until actual PDF ingestion needs it. Extracted references would still need identifier resolution; parsing does not establish citation validity. |
| [PaperKit](https://github.com/peternicholls/PaperKit) | [MIT](https://github.com/peternicholls/PaperKit/blob/master/LICENSE); head 2026-06-19, non-archived. | Reviewed academic writing/LaTeX workflow; do not adopt its multi-agent instruction framework. Canonical manuscript generation remains small and evidence-driven. |
| [PaperAgent local writing workspace](https://github.com/lachlanchen/PaperAgent) | No root license reported by [upstream README](https://github.com/lachlanchen/PaperAgent#license) or GitHub API; head 2026-09-12, non-archived. | Reject reuse because licensing is unresolved and a web writing IDE is outside Phase 1. |

No agent framework, vector database, PDF extractor, or LLM SDK is installed. Domain reasoning and defensible novelty require later researcher/provider input; a repository inventory alone cannot establish a publishable contribution.

## Metadata and citation verification

**Crossref: adopt a narrow direct REST adapter.** Its [official REST documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) describes publisher/member-deposited metadata, DOI resolution, bibliographic searches, and JSON responses. [Access documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) permits unauthenticated requests and recommends identifying polite requests. Store the actual response, request URL, retrieval time, and returned stable identifier. Check required bibliographic fields; search results are candidates until identifier metadata is retrieved. Metadata proves that the referenced bibliographic record exists, not that an arbitrary manuscript assertion is supported by its full text. Crossref says almost all metadata may be reused, but abstracts may carry copyright; do not treat returned abstracts as freely licensed article text.

**OpenAlex: defer the second provider.** The [official API reference](https://help.openalex.org/api/) says its data is CC0. [Current authentication docs](https://help.openalex.org/api/authentication/) (updated 2026-08-19) allow casual keyless queries and higher daily budgets with a free API key. These rules have changed over time: do not hardcode obsolete quotas, create accounts, or incur paid usage. Its graph can later expand literature and venue candidates without a Python wrapper.

**Semantic Scholar: defer.** [Official API terms](https://api.semanticscholar.org/license/) contain purpose, attribution, and access restrictions rather than a blanket open-source grant. A permissive client library does not override service/data terms. Crossref meets the initial need with fewer external assumptions.

Persist verified bibliographic metadata separately from any full-text evidence passages. Never create author names, titles, dates, DOIs, or results from model memory. Novelty search must record its limits and cannot justify a claim of being first merely by finding no match.

## Venue discovery and submission: research now, implement later

| Service / project | Official source and terms | Decision |
| --- | --- | --- |
| DOAJ | [Terms](https://doaj.org/terms/) explicitly place journal and article metadata under CC0; [API](https://doaj.org/api/docs) provides metadata access. | Phase 2 candidate discovery for open-access journals. It cannot independently verify SCIE/ESCI or current publisher submission requirements. |
| Clarivate Master Journal List | [Official search](https://mjl.clarivate.com/home), [official journal-search guidance](https://webofscience.help.clarivate.com/en-us/Content/search-aids.htm). Proprietary service, no software reuse license assumed. | Verify current Web of Science coverage from the authoritative provider when selecting venues; retain URL and verification date. No fixed journal list or inference from DOAJ presence. |
| Publisher guidelines / journal finders | [Elsevier Journal Finder](https://journalfinder.elsevier.com/) is a current discovery aid; individual publisher pages remain policy authority. | Defer adapters and scoring. APC, preprint, AI use, scope, declarations, and formatting require current official pages before submission. |
| Open Journal Systems | [GPLv3 license](https://github.com/pkp/ojs/blob/main/docs/COPYING), [official REST API source](https://github.com/pkp/ojs/blob/main/docs/dev/swagger-source.json); head 2026-09-29, non-archived. | Future adapter candidate for an actual target installation with authorized API access. Do not install the server or assume every journal grants author-side API access. |
| Editorial Manager | [Aries support](https://www.ariessys.com/support-and-resources/), [2025 web-services instructions](https://www.ariessys.com/wp-content/uploads/Customer-Instructions-Web-Services-and-Notification-Services.pdf). Proprietary services. | Integration availability depends on publisher/service configuration. No universal personal-author submission API established by this review; defer a specific API/browser adapter until a target journal exists. |

The application will not submit to a journal or preprint server in Phase 1. Later adapters must enforce one active peer-review submission per study/paper, confirmed withdrawal/rejection, current policy evidence, and explicit author attestation before final submission. CAPTCHA/MFA handling remains a human action. This record authorizes no account creation, paid service, external manuscript upload, or final submission.
