# Empirical Software Engineering — Research Article

Choose `emse` for an original or replicated empirical study of software engineering. Explain the research question, how cases or participants were selected, what was observed, how the data were analysed and what limits the conclusion. Qualitative field studies and controlled experiments can both fit. A working tool and passing tests can establish implementation behaviour; a claim about developer productivity or software quality needs evidence about that outcome.

## Official sources — checked 2026-11-06

- [Aims and scope, Research Articles](https://link.springer.com/journal/10664/aims-and-scope)
- [Submission guidelines, editorial procedure and Word formatting](https://link.springer.com/journal/10664/submission-guidelines)

Both publisher pages were read directly. The journal accepts editable Word files and explicitly provides **no journal Word template**. There is no publisher DOCX to download, hash or redistribute. Recheck the instructions for the selected article category when preparing the actual submission.

## Initial manuscript

- Review is single-blind. The title page identifies the authors, their affiliations, a corresponding author and active email, and available ORCIDs. Obtain these from the authors.
- Write a 150–250-word abstract and supply 4–6 keywords. A structured abstract is optional; if used, cover context, objective, method, results and conclusions.
- Use author–year citations and an alphabetical reference list with full DOI links where available. Use decimal headings up to three levels. Check the Word document for a plain body font (the journal gives 10-point Times Roman as an example), automatic page numbering, editable tables and equations.
- Include a data availability statement explaining access to the evidence or any restrictions. Obtain applicable statements under **Statements and Declarations**, including competing interests. Document substantive LLM use in Methods or another appropriate section; authors remain responsible for the work.

## Prepare editable files

From the authored manuscript directory, convert the Markdown to a new DOCX draft, e.g.:

```sh
pandoc paper.md --standalone --number-sections --output paper.docx
```

Author the citations and references in the journal's style, or resolve verified bibliographic records with Pandoc citeproc and check the result. Inspect the editable DOCX against the instructions before submission: ordinary Pandoc output does not certify layout, page numbering or citation style. This route does not use `export_manuscript.py`'s official-template preflight, Word conversion or native PDF measurement.

Use the [repository-to-draft workflow](repository-to-draft.md) for claim checking and the explicit bundle. After conversion and document edits, inspect the DOCX against the current authored source and [record the conversion files](tools.md#host-prepared-cs-manuscripts). Select the Markdown as `manuscript` so it matches the evidence report, the DOCX as `editable_docx`, and the saved `conversion.json` as `conversion_record`; include the bibliography and relevant editable artwork. Changes to the recorded inputs or output leave a regeneration gap in the bundle. Keep research and author gaps in the checklist. The publisher asks for all relevant editable sources at initial submission and revision; the authors review the system-generated PDF and make the submission decision themselves.
