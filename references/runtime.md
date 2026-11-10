# Host runtime and Claude installation

One `SKILL.md` and one set of scripts serve Claude Code, Claude.ai and other Agent Skills hosts. The host agent reads and writes the article; the scripts do not call an LLM API or require a provider API key. Do not duplicate the workflow in `CLAUDE.md` or add a model controller.

## Locate and use the installed skill

Resolve `scripts/`, `references/`, `assets/` and `requirements.txt` relative to the directory containing the loaded `SKILL.md`, not the user's repository or an assumed Codex/Claude path. Use that actual absolute path in the commands documented in [tools.md](tools.md). Put research inputs and generated outputs outside the installed skill.

Check only the prerequisites needed for the requested task. Use an available Python 3.11+ interpreter. If packages are missing and installation is authorized, use the host's managed environment or a workspace virtual environment with this skill's `requirements.txt`; do not change global packages, credentials or network policy. A metadata field or an installed skill does not install dependencies.

| Task | Prerequisite / boundary |
| --- | --- |
| Read sources, select a contribution and write prose | Host file/repository and literature access; no Python or LLM SDK is needed for reasoning |
| `research_workspace.py evidence`, `submission_support.py bundle` | Python 3.11+; these paths use the standard library |
| `research_workspace.py repository` | Python 3.11+, Git and permitted GitHub access; captures files, never executes the input project |
| Bibliography import | Python; `pyparsing` is used for BibTeX parsing; missing literature facts are not filled in |
| Preflight, document conversion, JOSS source export | Relevant dependencies in `requirements.txt`; JOSS also needs Pandoc and genuine YAML/BibTeX metadata |
| `export_manuscript.py export --docx-only` | Pandoc and document dependencies; Access/JORS also need the supplied official template. No Word/PDF or page verification is performed |
| Native Word/PDF export | Windows, PowerShell and an already installed/licensed Microsoft Word, plus the document dependencies; Access/JORS need the supplied official template |

For a document-environment problem, the existing diagnostic is:

```sh
python /absolute/skill/path/scripts/environment_check.py --output-dir /absolute/new/environment-report
```

Exit 1 here means native Word export prerequisites are incomplete. It does not mean prose writing, evidence checks or source bundling are unusable. Do not make this diagnostic a mandatory gate for every task.

## Claude Code

Install the repository or unpack the `paper-factory/` folder into either `~/.claude/skills/` (personal) or `.claude/skills/` (one project). Preserve its internal paths. Invoke `/paper-factory` with the repository URL or the specific revision/preparation request. A normal installation does not need `agents/openai.yaml`, a plugin manifest, custom hooks, tool pre-approval, an API key or a duplicated prompt.

```sh
git clone https://github.com/andongmin94/paper-factory.git "$HOME/.claude/skills/paper-factory"
```

On Windows PowerShell, replace `$HOME` with `$env:USERPROFILE`. Do not overwrite an existing skill installation or its uncommitted work.

## Claude.ai

Enable code execution and file creation, then open **Customize > Skills**, use **Add skill (+) > Upload a skill**, and upload `paper-factory.zip`. It contains a single top-level `paper-factory/` folder with uppercase `SKILL.md`. Enable the skill and ask, for example: "Use paper-factory to analyze this repository and prepare an evidence-grounded incomplete draft when required evidence is missing."

Network access depends on the account/admin configuration. Do not assume Git, publisher access, installed packages or Microsoft Word are available. When native Word export is unavailable, `export --docx-only` can prepare editable DOCX with conversion records if Pandoc and document dependencies are present. Include it alongside the authored Markdown, bibliography, necessary figures and existing bundle checklist; otherwise deliver those source files. Word/PDF verification stays pending. A generic built-in document renderer is not verification of this skill's native Word/PDF route. Do not install Word or switch journals merely to make export pass.

If Git or a publisher is inaccessible, report the exact blocked step and actual reading scope. Authorized connectors or supplied files can support explicitly identified source reading, but do not call that a successful repository-capture CLI run. Keep incomplete evidence/guidance conditional; do not invent missing metadata or claim an export that was not produced.

## Upload archive

The repository's existing CI makes an installable archive after its tests pass. It archives committed `SKILL.md`, `LICENSE`, `requirements.txt`, `scripts/`, `references/` and `assets/` with the `paper-factory/` prefix. It excludes `.git`, tests, CI configuration, historical work logs, the human-facing README and Codex UI metadata. It does not package manuscripts or account data. The same archive can be unpacked for Claude Code.

From a checked-out revision, the equivalent command is:

```sh
git archive --format=zip --prefix=paper-factory/ --output=../paper-factory.zip HEAD SKILL.md LICENSE requirements.txt scripts references assets
```

GitHub wraps a downloaded Actions artifact in another ZIP: extract that wrapper and upload the contained `paper-factory.zip`, not the outer artifact ZIP. Check the artifact's source commit before installing. Publisher assets keep the provenance in `assets/templates/provenance.json`; the repository MIT license does not relicense third-party templates. No new publisher templates or fonts are fetched during packaging.

## Verification scope

Archive structure and Python tests do not prove that Claude selected the skill, that its prose is scientifically adequate, or that a real repository-to-draft case completed. Confirm actual invocation in the target host separately. The hosted Claude API has additional no-network/no-runtime-install constraints and requires a separate integration; this change does not implement or verify one.

Official host documentation checked **2026-11-05** (not a journal-guideline verification). The direct **Add skill > Upload a skill** menu was also observed in Claude.ai on **2026-11-06**; observing this UI does not verify a successful upload or invocation.

- https://code.claude.com/docs/en/skills — discovery paths, `/skill-name`, and portable frontmatter.
- https://support.claude.com/en/articles/12512198-how-to-create-custom-skills — ZIP structure and metadata. The description is kept below the help page's stricter 200-character limit.
- https://support.claude.com/en/articles/12512180-use-skills-in-claude — code execution prerequisite and upload UI.
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview — different host network/dependency constraints.
