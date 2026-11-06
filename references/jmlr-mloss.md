# JMLR — Machine Learning Open Source Software

Choose `jmlr-mloss` for an open implementation of a nontrivial machine-learning algorithm, toolbox or scientific-computing language that contributes to the ML community. A general application that calls an LLM does not qualify on that fact alone.

## Decide from evidence

Read the [MLOSS instructions and review criteria](https://jmlr.org/mloss/mloss-info.html) and [journal submission instructions](https://jmlr.org/author-info.html) (checked 2026-11-06). Identify the public repository, reviewed version, recognized open-source license and evidence of active users or developers. Explain what the implementation adds relative to relevant alternatives. Distinguish measured results from descriptions of functionality. Document installation, supported platforms, examples, tests and contribution practices from the inspected revision.

Check prior publications about the software. A previously published method is allowed. If the software itself was the main subject of a peer-reviewed publication, MLOSS requests a repository document listing improvements and extensions, referenced in the cover letter. Leave a duplicate or an unsupported extension ineligible for recommendation as a fresh submission.

## Prepare the initial submission

Write the description in LaTeX, **up to four pages plus additional pages for references**. The manuscript uploaded for initial review is a PDF. Prepare a separate cover letter naming the track, version, repository, license and evidence of an active community; follow the journal instructions for overlap, editor/reviewer suggestions, conflicts, keywords and co-author consent. Obtain approvals and declarations from the authors.

Use the [official formatting guide](https://jmlr.org/format/format.html) and [official style and sample](https://github.com/JmlrOrg/jmlr-style-file/tree/f413f638b407af76074813f8f88a82a7a5a81e9d). At this revision the SHA-256 of `jmlr2e.sty` is `a430a875d561235951800e4e21d2631e18ddf0b369646ec276f43ea5080f27c3`. Obtain the unmodified style separately. No redistribution license was identified in that revision; the skill does not ship these files. Never copy the sample's authors, editor, dates or paper identifier into a draft.

In the authored source directory, with the official style in `$style_dir` and a local TeX installation, build:

```sh
TEXINPUTS="$style_dir:" latexmk -norc -pdf -interaction=nonstopmode -halt-on-error -latexoption=-no-shell-escape paper.tex
```

Inspect the log, bibliography, and every PDF page, including where references begin. Bind claims to the exact authored source. After the successful build, [record its authored inputs and output](tools.md#host-prepared-cs-manuscripts). Use the existing `submission_support.py bundle` to select that source (`manuscript`, plus `latex_source` when it is separate), bibliography, figures, actual review PDF (`review_pdf`), the saved `conversion.json` (`conversion_record`), any genuine cover letter (`cover_letter`), and preparation records. Changed or omitted conversion inputs leave a regeneration gap; rebuild before recording a new PDF version. Bundle success does not certify page length, eligibility or approval. If compilation is unavailable, deliver incomplete source with the official-style link and the missing PDF recorded. Native Word export does not apply.

**After acceptance**, follow the [final-source instructions](https://jmlr.org/format/authors-guide.html): supply a compilable LaTeX archive and, for MLOSS, a separate archive of the reviewed software. No specific author AI policy was established from the MLOSS and journal submission pages checked; record actual assistance and leave this policy for confirmation rather than importing another journal's rules.
