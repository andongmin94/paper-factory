# Journal of Open Source Software

Choose `joss` only for substantial, reusable research software with demonstrated research use and sustained public development. Current screening requires more than six months of public history, open-source practices and iteration. General applications, thin API wrappers, notebooks, or a future-use claim do not establish eligibility.

## Official sources — checked 2026-11-02

- [Submission and AI policies](https://joss.readthedocs.io/en/latest/submitting.html)
- [Current paper format](https://joss.readthedocs.io/en/latest/paper.html) and [current example](https://joss.readthedocs.io/en/latest/example_paper.html)
- [Inara original source template](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/example/paper.md), [bibliography example](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/example/paper.bib), and [JOSS defaults](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/resources/joss/defaults.yaml)

The retained source template is `assets/templates/joss/paper.md`, SHA-256 `046936692004a5612945221b0c4d126b885266413247d7e5aeb016dd6fafc28d`. Its [MIT license](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/LICENSE) and copyright notice are retained. Treat it as a syntax example: current journal instructions supersede its older sample sections and date. Never retain sample authors, claims, or references as facts about a user's project.

Metadata follow-up — 2026-11-09: checked [Pandoc's YAML parsing](https://pandoc.org/MANUAL.html#extension-yaml_metadata_block), [Inara's metadata template slots](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/data/templates/default.latex), and [JOSS's title rule](https://joss.readthedocs.io/en/latest/paper.html#title). This follow-up covers metadata parsing, image-retention scope and title guidance only.

Citation follow-up — 2026-11-09: checked Pandoc's [uncited-item selection](https://pandoc.org/MANUAL.html#including-uncited-items-in-the-bibliography) and [bibliographic-data rules](https://pandoc.org/MANUAL.html#specifying-bibliographic-data), with independent Pandoc 3.9 AST/citeproc probes. These checks did not run Inara or produce a PDF.

## Authoring and source output

Use YAML-frontmatter `paper.md` with title, authors, affiliation mappings, tags, date (for example `2 November 2026`), and `bibliography: paper.bib`. Current guidance is 750–1,750 words and requires Summary, Statement of need, State of the field, Software design, Research impact statement, and AI usage disclosure. Include References and applicable funding acknowledgments.

Author names may use a string in `name`, structured fields directly on the author or nested under `name`, or a `literal` name. Preflight follows [Inara’s name-field aliases, precedence and display order](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/data/filters/normalize-author-names.lua) without rewriting the supplied Markdown.

Use Pandoc citations (`@key`, `[@key]`) and matching BibTeX/BibLaTeX entries; cite full venue names. JOSS's Inara configuration selects APA author–date citations. Its CSL has a separate CC BY-SA 3.0 license and is not relabeled MIT or bundled here.

Citation checks resolve actual Pandoc Cite identifiers in the body and YAML metadata against the retained `paper.bib`, and still require at least one body citation. Only the top-level `nocite` field treats `@*` as a selector for all bibliography entries. Explicit `nocite` keys must exist even alongside `@*`; unknown keys block source export. This is deliberately stricter than Pandoc 3.9 citeproc, which silently ignores unknown `nocite` keys. A nested field such as `notes.nocite` has no selector exception. Empty values or values without actual Cite nodes add no keys.

Pandoc can also use inline CSL `references` metadata and let it override matching external records. This tool keeps `paper.bib` as its key-definition list: inline CSL is preserved as authored source, but is not interpreted as a citation database and cannot supply a missing key for these checks. Ordinary metadata `id` fields are not inferred to be citations. Source checks do not establish the complete citeproc rendering result.

The existing preflight/export CLI validates metadata, sections, citations and local media, then preserves `paper.md`, `paper.bib`, and referenced figures. Article metadata comes from YAML; `--profile` and `--template` are unsupported. See [tools.md](tools.md) for `--bibliography` and `--resource-dir`. Source files must ultimately accompany the software in its Git repository; export does not upload them.

Images parsed as Pandoc Image nodes in the body or YAML metadata use the same local-path and file checks and are retained at the same relative paths. The original manuscript and image bytes remain unchanged. Retaining an image does not establish that its metadata field or content meets journal policy; keep the title plain text as current JOSS guidance requires.

Use Markdown image syntax such as `![Caption](figures/plot.png)` so the exporter can copy the figure at the same relative path. Raw TeX `\includegraphics` and HTML `<img>` in the body or YAML metadata are unsupported by this exporter.

## Limits and human decisions

No Word or Inara PDF rendering runs in this path. Source checks cannot establish PDF layout or visual approval, and native-Word finalization does not apply. Image collection does not infer dependencies from plain path strings or raw HTML/LaTeX, or collect the complete Inara runtime and publisher assets.

For a separate PDF check, use the publisher's unchanged [Inara renderer](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/README.md). It supports Docker or its native Makefile. With the upstream Pandoc, LuaLaTeX, package and font requirements available, the native command is:

```sh
make -C /absolute/inara pdf ARTICLE=/absolute/source/paper.md JOURNAL=joss TARGET_FOLDER=/absolute/new/pdf-output
```

Inspect every output page and resolve missing references or rendering warnings before claiming final layout approval. A zero compiler exit alone does not establish this approval or current submission eligibility.

Disclose actual AI tools, assistance and human validation. JOSS bars AI-written author–editor/reviewer conversations except translation, and reserves reviewer judgments for humans. Keep automated review as author-side diagnostics; never infer human verification or consent. Actual software eligibility, review and submission remain separate from format checks.
