# Journal of Open Source Software

Choose `joss` only for substantial, reusable research software with demonstrated research use and sustained public development. Current screening requires more than six months of public history, open-source practices and iteration. General applications, thin API wrappers, notebooks, or a future-use claim do not establish eligibility.

## Official sources — checked 2026-11-02

- [Submission and AI policies](https://joss.readthedocs.io/en/latest/submitting.html)
- [Current paper format](https://joss.readthedocs.io/en/latest/paper.html) and [current example](https://joss.readthedocs.io/en/latest/example_paper.html)
- [Inara original source template](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/example/paper.md), [bibliography example](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/example/paper.bib), and [JOSS defaults](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/resources/joss/defaults.yaml)

The retained source template is `assets/templates/joss/paper.md`, SHA-256 `046936692004a5612945221b0c4d126b885266413247d7e5aeb016dd6fafc28d`. Its [MIT license](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/LICENSE) and copyright notice are retained. Treat it as a syntax example: current journal instructions supersede its older sample sections and date. Never retain sample authors, claims, or references as facts about a user's project.

## Authoring and source output

Use YAML-frontmatter `paper.md` with title, authors, affiliation mappings, tags, date (for example `2 November 2026`), and `bibliography: paper.bib`. Current guidance is 750–1,750 words and requires Summary, Statement of need, State of the field, Software design, Research impact statement, and AI usage disclosure. Include References and applicable funding acknowledgments.

Author names may use a string in `name`, structured fields directly on the author or nested under `name`, or a `literal` name. Preflight follows [Inara’s name-field aliases, precedence and display order](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/data/filters/normalize-author-names.lua) without rewriting the supplied Markdown.

Use Pandoc citations (`@key`, `[@key]`) and matching BibTeX/BibLaTeX entries; cite full venue names. JOSS's Inara configuration selects APA author–date citations. Its CSL has a separate CC BY-SA 3.0 license and is not relabeled MIT or bundled here.

Use Markdown image syntax such as `![Caption](figures/plot.png)` so the exporter can copy the figure at the same relative path. Raw TeX `\includegraphics` and HTML `<img>` are unsupported by this exporter.

The existing preflight/export CLI validates metadata, sections, citations and local media, then preserves `paper.md`, `paper.bib`, and referenced figures. YAML is authoritative; `--profile` and `--template` are unsupported. See [tools.md](tools.md) for `--bibliography` and `--resource-dir`. Source files must ultimately accompany the software in its Git repository; export does not upload them.

## Limits and human decisions

No Word or Inara PDF rendering runs in this path. Source checks cannot establish PDF layout or visual approval, and native-Word finalization does not apply.

For a separate PDF check, use the publisher's unchanged [Inara renderer](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/README.md). It supports Docker or its native Makefile. With the upstream Pandoc, LuaLaTeX, package and font requirements available, the native command is:

```sh
make -C /absolute/inara pdf ARTICLE=/absolute/source/paper.md JOURNAL=joss TARGET_FOLDER=/absolute/new/pdf-output
```

Inspect every output page and resolve missing references or rendering warnings before claiming final layout approval. A zero compiler exit alone does not establish this approval or current submission eligibility.

Disclose actual AI tools, assistance and human validation. JOSS bars AI-written author–editor/reviewer conversations except translation, and reserves reviewer judgments for humans. Keep automated review as author-side diagnostics; never infer human verification or consent. Actual software eligibility, review and submission remain separate from format checks.
