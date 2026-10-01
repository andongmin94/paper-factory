# Autonomous repository research

The new workflow connects a user's repository or GitHub profile to a bounded
software experiment and an evidence-linked English manuscript. The intended V1
scope is small Python/Node CPU components with measurable behavior, an explicit
comparison and a checkable oracle. Repository selection alone is not research.

## Current readiness and completion criteria

The installed CLI exposes repository selection, run/batch, status, cancellation,
resume and verification. The picker retrieves actual public GitHub metadata and
optionally inspects small manifests and READMEs. Persistent checkpoints connect
protocol generation, literature, code generation/review, isolated execution,
trusted analysis, manuscript generation/review and native export.

Verification has distinct scopes. On 2026-10-01, the native Windows controller
completed an actual structured model request with the private official Codex CLI
0.159.3: the application reported `verified: true` and the returned JSON contained
`ready: true`. The request record is preserved in the temporary
`paperfactory-windows-final-model-probe-7zl7jezw/call` evidence directory. This verifies
the current account's model authentication and controller network access; it does
not establish completion of a live model-generated study or paper.

The production browser workflow also imported a synthetic local project,
executed its descriptive inventory, generated a PDF and completed integrity
verification. `scripts/start_windows.ps1` ran successfully from a repository path
containing Korean characters. Unsaved manuscript edits survived result refresh
and stage changes, and no browser CSP violations were observed. This is a
local template workflow check, not evidence of autonomous live inference.
Native isolation integration and the full test results are recorded separately
in [status.md](status.md).

The recorded checks below describe the earlier cloud environment; their
authentication outcomes do not establish the current Windows account's state.

| Check | Observed scope |
|---|---|
| Repository picker | 42 tests passed; a live public profile lookup considered 17 actual repositories |
| Pipeline integration | 23 tests passed using explicitly simulated model, runner and literature inputs; real trusted analysis, Pandoc/Typst PDF, DOCX, TeX and ZIP checks executed |
| Independent reproduction | Bundled standard-library analysis was rerun from raw fixture observations and matched the reported results |
| Live subscription generation | The actual application run stopped in plan with AUTH_REQUIRED (HTTP 401); an earlier transport probe encountered HTTP CONNECT 403. No generated protocol or autonomous paper was produced; successful live generation remains unestablished |
| Official web login | The actual 0.8.0 device-login checks with official CLI 0.159.0-alpha.3 and 0.159.3 ended with LOGIN_START_TIMEOUT and confirmed worker cleanup; no approval code was issued. A separate HEAD request to the approval page returned HTTP 530 |
| Subsequent actual model request | Stable CLI 0.159.3 dispatched a request using the supplied ChatGPT login; the model server returned HTTP 401 and requested signing in again. No model output or usage was returned. A later 180-second device-login startup retry still issued no code |
| Fresh source preparation | Actual public Git snapshots for madi, garak and mini-cast were imported, pinned source hashes verified and specified production functions included in bounded context. No new protocol, observations or paper exists yet |

Simulation checks are not evidence of live model inference, production-call
execution or platform isolation. A saved network-configuration draft does not
apply settings to the current machine or verify connectivity. After the required
runtime access is available, repeat the live run and its independent verification.
The earlier three delivered studies were designed and executed outside this
autonomous workflow; they are not proof of its autonomy.

Completion requires a fresh source import, model-generated protocol and experiment,
actual sandbox observations, reproducible host-side analysis, grounded manuscript,
native exports and a verification report. Missing prerequisites or evidence must
produce a blocked/failed state instead of a successful paper. Final scientific
approval belongs to the author. This workflow does not automatically submit to a
journal, publish a preprint or attest authorship.

## Native Windows setup

Use Python 3.11+ (3.12 recommended), Git, and Node.js 24 with npm in PowerShell.
The [Windows setup helper](../scripts/setup_windows.ps1) prepares the virtual
environment, document/analysis dependencies and a private official Codex CLI.
The equivalent manual installation is:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,pdf,research,automation]" pypandoc_binary -r scripts/research-runtime-requirements.txt
npm.cmd install --prefix .venv/codex --no-audit --no-fund @openai/codex@0.159.3
$env:PYPANDOC_PANDOC = (& .\.venv\Scripts\python.exe -c 'import json; from pathlib import Path; import pypandoc; p = Path(pypandoc.get_pandoc_path()); print(json.dumps(str(p if p.is_file() else p.with_suffix(".exe"))))') | ConvertFrom-Json
Copy-Item .env.example .env
.\.venv\Scripts\paperfactory.exe --env-file .env auto doctor
```

The private npm installation stays inside the virtual environment and preserves
an existing global Codex CLI. The controller detects its private
`codex.cmd` launcher and invokes Node with the official `codex.js` entry point;
it does not run the launcher through a shell. `PF_CODEX_BIN` can select a different
trusted installation. Python's full standard library is required; a small
embedded interpreter without that library cannot serve as the experiment runtime.

Windows generated experiments run in an AppContainer without network
capabilities. Source, generated code and the staged interpreter are read-only;
work/output/temp directories are private writable locations. A bounded Job Object
owns the complete process tree, including timeout and cancellation cleanup.
Windows requires neither Docker nor `PF_RESEARCH_IMAGE`, and does not invoke
`build_autonomous_image.py`. If native isolation is unavailable, the pipeline
blocks without unrestricted execution.

Windows AppContainer grants access according to Windows ACLs, including shared
standard OS resources. The execution receipt therefore records
`read_only_root: false`. Disk usage is monitored in writable directories rather
than enforced by a filesystem quota; memory, process and CPU limits use the Job
Object. These enforcement details remain in the exported execution receipt.

Only controller-approved package groups enter a generated experiment. The setup
helper installs `scripts/research-runtime-requirements.txt` into its virtual environment;
`auto doctor` lists the groups whose exact versions are available. NumPy and
Matplotlib installed by the research extra support trusted controller analysis
and do not make arbitrary experiment dependencies available.

Linux retains the Docker research backend. Its optional image provisioner,
`scripts/build_autonomous_image.py`, uses Linux runtime binaries and `ldd` and
records an immutable `PF_RESEARCH_IMAGE=sha256:...` identity. Linux autonomous
execution requires that provisioned image; Windows does not use it.

## Connect the official Codex CLI

Use the official [Codex CLI](https://github.com/openai/codex) with an existing
supported ChatGPT subscription login. The CLI manages its own credentials.
Paper Factory calls its noninteractive `codex exec` interface; it does not extract
OAuth tokens, copy credential files or implement a separate subscription API.
An OpenAI API key is not required for this subscription-backed adapter.
Every model request rechecks ChatGPT authentication and sets the official CLI's
`forced_login_method="chatgpt"`; changing to API-key authentication after an
assessment checkpoint blocks subsequent generation, including resumed runs.
Subscription usage limits still apply, and an unavailable login or model blocks
the pipeline. Login begins only after the user clicks the web connection button
or runs `paperfactory auto login`; setup and status checks never launch it.

The web's **ChatGPT 구독으로 연결** button runs the official
`codex --no-daemon -c 'cli_auth_credentials_store="file"' login --device-auth` in a fresh,
private worker profile. Enter the displayed one-time code at the official
`https://auth.openai.com/codex/device` page. Passwords and account approval remain
on OpenAI's page. After approval, click **실제 모델 요청 확인** to make a bounded
structured model request. CLI `auto login` performs that request after approval.
Login recognition alone does not select the new connection.

The controller stops login startup if no official address and code arrive within
60 seconds; a received code permits up to 15 minutes for account approval.

Private profiles live under `PF_CODEX_AUTH_HOME` (default `PF_HOME/codex-auth`),
outside Git, with owner-only directories. The official CLI manages its own
credentials; the controller never reads or copies credential contents. Only a
successful probe atomically writes the nonsecret `active.json` selection pointer.
Research workers use that selected profile without changing the environment's
original `CODEX_HOME`. A failed replacement login leaves an earlier connection
selected. Connection status contains a timestamp for the last successful actual
request; it does not guarantee future quota or token validity.

Login/probe cancellation and server restart preserve a cleanup block when worker
termination cannot be confirmed. GET status performs no login or model request.
Connection endpoints require the local server and exact same-origin writes;
public article preview cannot read login codes or start authentication.
**연구 작업자 연결 해제** removes the selection; it does not revoke the account's
OpenAI session or erase official credentials. For credential revocation, use the
official account/CLI controls for that private profile. Existing injected platform
authentication is preserved and can still be used by legacy CLI configurations.

Commands: `auto connection`, `auto login`, `auto probe`, `auto login-cancel` and
`auto disconnect`. API keys and OAuth tokens do not belong in `.env` or chat.

Configure the following locally, alongside private author metadata:

| Setting | Purpose |
|---|---|
| `PF_CODEX_BIN` | Optional trusted CLI path; defaults to the private venv npm installation, then `PATH` |
| `PF_CODEX_MODEL` | Optional model available to the logged-in CLI account |
| `PF_NODE_BIN` | Optional native Windows `node.exe` path; defaults to `PATH` |
| `PF_CODEX_AUTH_HOME` | Optional private official-login connection root outside Git; default `PF_HOME/codex-auth` |
| `PF_RESEARCH_IMAGE` | Linux Docker backend only: provisioned local image identified by immutable SHA-256 digest; unused on Windows |

Select local configuration explicitly with `paperfactory --env-file .env ...`.
Existing process settings take precedence over the selected dotenv file. Keep
real `.env` files and generated workspace data out of Git. The official CLI's
credential store remains under its own control and never enters generated code.

## Pipeline and evidence boundaries

1. **Select and import.** Accept a repository or rank up to three repositories from
   a GitHub owner/profile. The picker excludes forks, archived/disabled/private/empty
   repositories, unsupported primary languages and GitHub-reported sizes above
   100,000 KiB. It considers at most 300 records, inspects at most ten candidates
   and caps requests, elapsed inspection time, responses and decoded files.
   Library/CLI entrypoints, controlled-test structure and small dependency sets
   improve the score; workspace/native build requirements reduce it. A dependency-free
   monorepo root does not establish dependency-free components. No repository name
   receives a special preference. A score
   does not establish a suitable question, passing tests or CPU-only execution.
2. **Assess and plan.** The model reads bounded source context and proposes a
   question tied to actual source files, at least two conditions, metrics, an
   independent oracle, sampling units, seeds, analysis and limitations. Preserve
   the versioned protocol before experiments. The protocol names a production
   source file and callable; execution requires the controller's instrumented
   call receipt for that target. Record instrumentation in the methods, especially
   for timing measurements. Reject plans whose required runtime,
   data, permissions or comparison cannot be provided.
3. **Retrieve literature.** Preserve bibliographic metadata and distinguish
   inspected abstracts from inspected full text. Claims require matching source
   evidence; DOI existence and a model's memory are insufficient. Missing critical
   evidence must block unsupported discussion or final completion. Never claim
   novelty solely because a search returned few papers.
4. **Generate and execute.** Keep generated code separate from the frozen imported
   source. Windows selects the native AppContainer/Job Object runtime; Linux
   selects the provisioned Docker runtime. Both deny network access, provide
   read-only source/code/runtime inputs and bound memory, processes, time and
   output. Keep each platform's enforcement and provenance in the execution
   receipt. Unavailable isolation blocks the experiment. Never send model
   credentials or author configuration to generated programs. Dependencies must
   already be approved and available in the selected runtime.
   A separate model pass reviews code against the frozen plan and source before
   execution. This is assisted review and does not prove oracle independence.
5. **Analyze and write.** Treat observed rows separately from proposed outcomes.
   Trusted analysis validates conditions, sample IDs, metric values and oracle
   results and computes tables/figures. Bind manuscript numerical claims to these
   outputs and citations to inspected passages. State denominators and repeated
   versus independent observations. Negative results are valid; repairing an
   execution failure must not become selecting only favorable outcomes.
   Failed scientific controls retain their observations and block the run. They
   do not trigger code regeneration to obtain a passing result. Manuscript review
   checks interpretation against the protocol, computed values and supplied
   literature excerpts; it supplements author review.
6. **Export and verify.** Preserve source/protocol/code hashes, model-call provenance,
   raw observations, analysis, literature reading scope and native manuscript
   files. Check hashes, reopen exports and retain reproduction instructions.
   A completed draft is not scientific peer review or journal acceptance.

## Control, recovery and acceptance

Use the installed commands from the same development environment. On Windows:

```powershell
.\.venv\Scripts\paperfactory.exe --env-file .env auto doctor
.\.venv\Scripts\paperfactory.exe --env-file .env auto select https://github.com/OWNER --count 3
.\.venv\Scripts\paperfactory.exe --env-file .env auto run https://github.com/OWNER/REPOSITORY
.\.venv\Scripts\paperfactory.exe --env-file .env auto batch https://github.com/OWNER --count 3
```

The run command reports its workspace and pipeline ID. To inspect or control an
existing run, select that workspace explicitly; cancellation can be requested
from another terminal while its worker is active:

```powershell
.\.venv\Scripts\paperfactory.exe --env-file .env --workspace C:\research-workspaces\example auto status PIPELINE_ID
.\.venv\Scripts\paperfactory.exe --env-file .env --workspace C:\research-workspaces\example auto cancel PIPELINE_ID
.\.venv\Scripts\paperfactory.exe --env-file .env --workspace C:\research-workspaces\example auto resume PIPELINE_ID
.\.venv\Scripts\paperfactory.exe --env-file .env --workspace C:\research-workspaces\example auto verify PIPELINE_ID
```

With an activated Linux virtual environment, use `paperfactory` and an appropriate
Linux workspace path for the same commands.

Run and batch share the typed pipeline. A project permits one queued/running job.
Resume verifies frozen source, code, observations and literature hashes and retries
only the unfinished stage. Interrupted attempts and successful experiments are
retained. Cancellation requests stop active work while preserving diagnostics.
Use `paperfactory auto --help` and individual command help for supported budgets.

Budgets bound model calls, repair attempts, total elapsed time and individual
model/experiment timeouts. Authentication, account limits, network failures,
unavailable isolation, infeasible protocols and missing evidence have explicit
diagnostics. A run must not bypass those states or replace measurements with
generated prose. Resuming does not reset consumed budget without an explicit
new run or supported configuration change.

The decisive acceptance check uses a previously unprepared small repository,
without Codex manually writing its protocol or experiment. Invoke the installed
application with repository input and configured prerequisites, then independently
recompute manuscript claims from the newly recorded raw observations. Exercise
unavailable authentication/isolation, interrupted work, bad generated output and
unsupported citations as well as successful completion. Mocked provider/runner
tests verify orchestration contracts; they do not prove live model execution or
platform isolation. Native AppContainer executions and Docker executions are
separate acceptance evidence. Record live checks separately and state anything unrun.
