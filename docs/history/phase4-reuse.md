> 역사 자료: Paper Factory 0.12.0 플러그인·호스트·수동 연구/투고의 기록입니다. 독립 앱의 현재 설치·사용 안내가 아닙니다. 기존 측정과 검증 주장을 새 앱의 성공으로 계산하지 않습니다.

# Phase 4 reuse and revision boundaries

Reviewed on 2026-09-30, before implementing the revision workflow. The existing
dependency set, approved freezes, experiment/evidence records, Pandoc/Typst
renderer, citation processor, and transactional publication journal were inspected
first. Phase 4 needs no additional runtime dependency.

| Component | Primary source and license | Decision |
| --- | --- | --- |
| Python `difflib` | [Standard-library documentation](https://docs.python.org/3/library/difflib.html), [PSF license](https://docs.python.org/3/license.html) | Adopt unified line diffs between the frozen parent and revised canonical text. Keep the original input bytes and hashes alongside the comparison. Text changes do not establish scientific equivalence or satisfy a request for a new experiment. |
| Existing evidence, freeze and publication modules | Repository code and [Phase 3 reuse decisions](phase3-reuse.md) | Reuse strict Pydantic records and SQLite transactions. Create a new paper version within the same study; preserve the approved parent. Link the revised package and author attestation to the original active journal submission, with its existing external identifier, instead of opening another submission slot. |
| Existing Pandoc, Typst and citeproc rendering | [Pandoc manual](https://pandoc.org/MANUAL.html), [existing renderer/license review](pdf-reuse.md) | Reuse the working conversion and verified bibliography path for revised manuscripts and response letters. Preserve evidence links in the local review artifacts. Formatting and citation conversion do not supply reviewer evidence or validate a scientific response. |
| Git diff | [Official documentation](https://git-scm.com/docs/git-diff), [GPL v2 license](https://github.com/git/git/blob/master/COPYING) | Keep Git available for developer review. `git diff --no-index` can compare files without repository history, but the application can produce its own canonical text comparison with `difflib`; no Git runtime dependency or copied implementation is needed. |
| latexdiff | [Maintained repository](https://github.com/ftilmann/latexdiff), [CTAN release and GPL v3 license](https://ctan.org/pkg/latexdiff) | Defer. The current 1.4.0 release was announced on 2026-01-02 and compares LaTeX through Perl; a rendered marked-up PDF also requires an appropriate TeX toolchain. Canonical Markdown/JSON comparisons meet the present local requirement. If a selected publisher requires marked-up native LaTeX, integrate the maintained tool with compilation checks rather than inventing a TeX differ. |
| PKP Open Journal Systems 3.5 | [Official API specification](https://github.com/pkp/ojs/blob/stable-3_5_0/docs/dev/swagger-source.json), [editorial decision documentation](https://github.com/pkp/pkp-docs/blob/main/dev/documentation/en/decisions.md), [GPL v3 license](https://github.com/pkp/ojs/blob/main/docs/COPYING) | Defer a publisher adapter until a journal, installation version and authorized author account are selected. The documented file and decision APIs are role/stage dependent. Author uploads to the review-revision file stage require revisions to have been requested. Creating an editorial decision can trigger stage changes and emails; it is not an author resubmission endpoint. A file upload alone does not demonstrate final revision submission. Avoid private backend endpoints that the specification discourages for third parties. |

The local workflow records a human-reviewed editor/referee report with preserved
source evidence and explicit comment quotations. It cannot authenticate an
arbitrary local report as an editor's message. Each response connects a specific
comment to manuscript sections, approved claims or actual experiment records,
and states whether it accepts, partially accepts or disagrees with the request.
If new analysis is required, old runs or a prose-only promise cannot stand in for
newly executed and validated work.

Scientific revisions belong to a new paper version. The parent freeze remains
unchanged, and the new manuscript must pass the existing evidence checks and
receive its own author approval. A response letter, report, comparison and
revised package must be bound by hashes before the final local revision
attestation. An edit after attestation invalidates that binding. The original
submission stays active throughout preparation and submission of the revision.
For an anonymous review policy, reuse the existing author redaction and export
identity checks to produce a separate reviewer response. Keep the preserved
author response, source plan, evidence bindings and comparison as administrative
audit files, with explicit file roles in the delivery instructions.

An imported, author-confirmed publisher receipt can record that a revision was
received, with the same external submission identifier. Actual browser/API
resubmission requires the selected publisher's present workflow, credentials,
permissions and final confirmation to be verified separately. No account,
external upload, editor message, dependency installation or paid service was
created during this research. The hosted PKP API documentation was inaccessible
in this review; the official repository specification and decision documentation
were readable.
