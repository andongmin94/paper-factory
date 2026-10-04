# Environment support goal

The requested outcome is one Paper Factory plugin with the same research and
export contract in Work Cloud, local Work/Codex on Windows and macOS, and ordinary
ChatGPT Chat. Docker, WSL, operating-system feature changes and user-managed
runtime installers are excluded. This goal started on 2026-10-04.

The frozen 0.10.2 ZIP and its five completed Cloud studies are retained unchanged.
The working installation remains frozen 0.11.0. A separate private 0.12.0 preview
is installed for regression; current source development has explicit provided-host
preparation. Installing a plugin does not itself establish any environment's
execution support. The bounded compatibility criteria are supported by the final evidence below; goal status is recorded separately.

| Environment | Current observed result | Explicit limits and future checks |
| --- | --- | --- |
| Work Cloud | Five retained studies; installed 0.11.0 and separate private 0.12.0 preparation/conversion/readiness regressions passed | Validate the next source increment and keep the working-installation upgrade separate |
| Windows local | New 0.11.0 study exported and all seven PDF pages reviewed; installed Codex 0.11.0 and corrected 0.12.0 preview readiness passed under approved host-tool permissions | Default retained-state access failed; new source release regression and installation remain distinct from these preview checks |
| macOS local | Actual ARM and Intel native CI passed preparation, conversion, readiness and mandatory lifecycle tests; original artifact bytes independently verified | Evidence covers hosted native Mac CI; personal Mac installation has not been tested |
| Ordinary Chat | Original distribution reached native Files; provided-host preparation and one controlled study completed/exported with externally reviewed manuscript, original artifact audit and six-page PDF QA | Fresh reviews used external Codex; standalone native review and single-conversation automatic production remain unproved |

## Implementation and verification scope

1. Separate private host preparation from the shared JSON research controller.
   Prepare complete platform dependencies and trusted runtime assets without
   modifying the host interpreter, system PATH or installed plugin resources.
2. Add Windows owned-worker termination/recovery and a macOS implementation.
   Preserve the existing Linux behavior and bounded Wasm/source-call evidence.
3. Establish ordinary Chat resource delivery using actual installed resources or
   a verified distribution mechanism, without counting manual ZIP attachment as
   plugin-install-only success. Test execution-space versions and permissions.
4. Run Windows preparation, isolation/cleanup and a complete new paper export.
   Validate the new package and regress the shared research/export behavior.
5. Run ordinary Chat preparation and a complete paper export when its actual
   resource delivery and tools permit it. Record concrete failures separately.
6. Test macOS code/platform decisions here, then obtain actual macOS execution
   evidence before calling macOS support verified. No Mac host is available in
   this session at the start of this goal.

## Completion evidence

Retain exact commands, exit codes, runtime/dependency identities, original
observations, cleanup receipts, reviews and verified delivered PDF bytes.
Mocked platform tests are not macOS execution evidence. Converter diagnostics
are not research papers. A manual attached package can test compatibility but
does not establish automatic plugin resource delivery.

Previous readiness observations are in
`.paper-factory/portability-probe/2026-10-04/verification-summary.json`.

## Retained increments on 2026-10-04

- Windows actual QuickJS basic/Unicode/source separation and unavailable ambient
  capabilities passed. Fresh readiness also exercised owned forced termination.
- Actual Windows private preparation with the current HTTPX/SOCKS helper passed:
  complete isolated dependencies, private Node 24.21.0, controller import, inherited
  HTTPX initialization, and native PDF/DOCX/TeX converter diagnostics. The exact
  development snapshot and results are retained under
  `.paper-factory/host-preparation-0.11.0-current/`; this is not a research export.
- The launcher verifies prepared Python/Node/Pandoc identities without changing
  system PATH or inherited proxy/TLS settings. Host-context and conversion checks
  passed 30 tests with actual document output verification.
- macOS guardian code was implemented before an actual Mac host was used.
  Its platform tests and the later remote CI results remain separate evidence.
- Ordinary Chat cannot read installed binary QuickJS/Typst resources through
  `skills__read`. Direct container HTTPS requests failed DNS; the native remote
  download broker rejected the exact wheel URL at its prior-web-view gate.
- A separate installed private 0.0.1 transfer probe passed exact manifest/chunk,
  decoded archive, original 1024-byte fixture and saved-file hashes in ordinary
  Chat. It used a small opaque resource-text relay with stdlib data decoding,
  without executing payload code or attaching a ZIP to the conversation. This
  proves that small transfer only, not whole controller/runtime delivery.
  Original evidence ZIP: 5298 bytes, SHA256
  `14ea0841d009128da62b541ea5d3f16af424b93bd3bd59db74908f1c516c6327`,
  retained in `.paper-factory/portability-implementation/2026-10-04/web-chat/`.
  The original ordinary Chat transcript is retained privately with that evidence.

- Final shared 0.11.0 ZIP is 1357197 bytes, SHA256
  `11b3fb20c9eb61d12f56918176ed089738d22975cf5634302317e62e50dcd70c`.
  Installed inventory SHA256 is
  `d126e509dac16954657cea1f2d8334aa9da8ba13796cad8a7f5bbde3b82a777a`.
  It was uploaded as a private new version; no public publication occurred at
  that release-upload checkpoint.
- Windows owned-worker and boundary tests passed 108/108; shared controller and
  workflow tests passed 72/72. Independent instruction forward review found no
  blocking interface contradiction. Actual Mac execution was unobserved at that
  Windows-test checkpoint.
- A new Windows Frontron study `research-73b2dea0df76` ran once and reached
  analyzed with confirmed cleanup: 96 raw rows, 99 retained fixtures and 51
  actual gate attempts. Two scientific controls passed. Manuscript review and
  original export delivery are the next required stages; these observations do
  not reuse earlier Cloud measurements.
- The same new Windows study subsequently passed fresh independent manuscript
  review and its first submit/export. Final state is completed/exported with one
  execution, one code submission, one draft submission and confirmed cleanup.
  All six actual exports and 29 command receipts were independently verified.
  The delivered PDF is seven pages, 107690 bytes, SHA256
  `0aeb00a31d888b2e3f2ff9140ce6745c6041a649582f3920dab816db1e3ba8cb`.
  Every page was rendered with bundled Poppler and visually inspected without
  changing the document or rerunning the study. The verified user-facing copy
  is `output/pdf/frontron-command-option-validation-windows.pdf`; Word, TeX,
  Markdown, validation and the original reproduction ZIP are under
  `output/windows-study/`. The end-to-end receipt is
  `.paper-factory/portability-implementation/2026-10-04/windows-study/windows-end-to-end-evidence.json`.
- The exact new installed package also passed actual Work Cloud preparation,
  private controller/import and PDF/DOCX/TeX converter diagnostics, then fresh
  QuickJS readiness with confirmed cleanup and an empty final journal. No study
  was executed in this regression check. Independent evidence review passed
  with explicit limits: the outer distribution ZIP was not mounted there and
  individual forced-kill receipts are not CLI outputs. Cloud evidence ZIP is
  1728613 bytes, SHA256
  `f47c61e9e2d8f4ea809f0bd115669eed456f2eab4a79adf6ffd83824d48401a3`.
  The original Work Cloud transcript is retained privately with that evidence.
- Ordinary Chat's existing HTTPX initialized with inherited policy but its one
  official PyPI request failed with ConnectError. The official PyPI release
  page was readable, but binary web-view rejected application/octet-stream.
  No network policy change, dependency installation or study was performed.
  Consolidated original evidence ZIP is 12303 bytes, SHA256
  `5ab2f6e176367dabfeb24deba10eb914ab3369ba5498191b0119d8672bc49194`.
- A separate private whole-package byte-transfer prototype contains every
  original 0.11.0 ZIP byte in 111 hash-pinned text chunks (1809707 encoded bytes).
  Local restoration verified all 46 original files and 41 inventory entries;
  its actual ordinary Chat first-three-chunk pilot passed. Local full
  restoration is not Chat whole delivery or execution evidence.
- Whole-package transfer attempt 001 stopped at a JavaScript relay wrapper's
  missing TextEncoder, before helper execution or any chunk request. The actual
  manifest/helper resource reads returned, but original filesystem bytes were
  not verified. This is a wrapper failure, not evidence of a resource gate
  rejection or proof that a direct nested writer is unavailable. Its original
  failure ZIP is 5176 bytes, SHA256
  `b014afe200bede70dd89618b8e31012edf683cdb3bb928e9e689a5e0c53c33ac`.
  A separately numbered attempt 002 tests a compatible original-text relay;
  attempt 001 and its reported post-failure discovery deviation are preserved.
- Attempt 002 verified the actual original manifest in ordinary Chat's execution
  filesystem: 14320 bytes, SHA256
  `c2d9a5a2b3880f6d1de61a4b2c24c5bcd949b2fa035dacbcf808550231a0a6e6`.
  The next helper relay failed strict Base64 decoding with `Excess padding not
  allowed`, exit 1, before helper execution or any chunk request. The original
  failure ZIP is 12237 bytes, SHA256
  `37c7e2e4877d30ea24200cb613f64950a5b63b0654b51fd065077b667e532def`.
  This proves one larger text-resource transfer, not the three-chunk pilot or
  complete controller delivery. Separate attempt 003 tests direct original ASCII
  text in native structured arguments and records the actual available writer
  catalog before making claims about a programmable bridge. No preparation or
  research is authorized within that diagnostic.
- Attempt 003 preserved the actual 10530-byte helper received by native
  structured arguments, SHA256
  `4c9ff06fb3ee83606a464be4631ac6dacc2ac014aa100f9895f6d8fe08ae3fdc`.
  It stopped before any chunk/helper execution because the original pin failed.
  Root inspected those downloaded bytes: appending exactly one terminal LF
  produces the original 10531-byte helper and original SHA256
  `57573c9ce23e5d2761b9966524e6e610c6c52a4dccf699e1e9d305f6b35e3a9c`.
  The actual current functions.exec writer catalog did not expose a directly
  callable native container writer; this does not establish that every possible
  bridge is absent. Original attempt-003 ZIP is 15051 bytes, SHA256
  `5900815b2398b4b1ef54e9bcf76403b806798757725844fab82ef4cd11399ef6`.
  Separate attempt 004 tests this explicit terminal-LF transport repair and the
  first three original chunks, keeping full-package delivery and execution
  unverified. No source body or expected digest is changed by that diagnostic.
- Attempt 004 passed the actual ordinary Chat first-three-chunk pilot. The exact
  original helper and three 16385-byte text chunks were verified after explicit
  single-terminal-LF transport repair; each decoded chunk is 12288 bytes.
  The original helper ran once, exit 0, stdout 1060 bytes, stderr empty, and
  reported `stage=chunk-pilot`, `chunks_verified=3`, `chunks_total=111`,
  `package_verified=false`. The target package directory remained empty; no
  dependency preparation, package execution or research occurred. This is an
  opaque model relay with recorded LF repair, not a direct programmable bridge.
  Original success ZIP is 99877 bytes, SHA256
  `05dcb5bad5e60a583757a829f39f943e65d926d057dad9a6383958aaa125ca94`.
  The original transfer-check transcript is retained privately with that evidence.
- A separate read-only native-files capability check found no exact visible
  `paper-factory-0.11.0.zip` file ID in this Chat's native conversation listing
  or one exact-title Library query. Four visible conversation files were the
  retained diagnostic ZIPs; two Library results were other diagnostic JSON files.
  `files__materialize` was exposed but requires an actual returned file ID, so
  no materialization, CRC/inventory check, upload, publication or execution was
  performed. This is a bounded current-surface result, not proof of platform-wide
  impossibility. Original evidence ZIP was downloaded and verified: 2374 bytes,
  SHA256 `12c899fc4ca1159a6c6b4b011424e2853c3f275c0a56ebd30b12f45e918337b9`.
  Complete 111-chunk model relay is not treated as a suitable installation
  experience merely because three chunks pass.
- Independent review of attempt 004 verified all 34 evidence ZIP members, 25
  tracked hashes, exact repaired original helper/chunks, and the decoded 36864-byte
  prefix against the frozen 0.11.0 ZIP. It accepts only the first-three-chunk pilot;
  complete package delivery and execution remain unverified. The review receipt is
  `read-only/attempt-004-transfer-review.json`, SHA256
  `953f3782445e76072f21bbdb7f4e4e6d58ff89b1b6bd07ac6cf95fb1e95b4acf`.
- The initial provided-host preparation design recorded the observed
  ordinary Chat modules and then-remaining blockers: Node 22 was rejected by the
  frozen 0.11.0 Node-24 gate, Typst was absent, and a pdflatex path alone was not verified
  PDF production. The proposed mode uses actual native interpreter identity and
  module/executable receipts, without fake private-venv claims, installation or
  network-policy changes. No provided-host source implementation or execution
  support is claimed from that design.
- A second bounded native Files metadata check exposed seven tools. Its
  `files__manage_library` upload accepts an existing container path or real file
  reference, not raw content; `skills__read` returns text strings. No documented
  in-memory content writer was exposed in this Chat, so no new file upload or
  payload execution was attempted. Writing a tiny diagnostic JSON into the
  old scratch failed because those paths had become read-only. The actual UI
  transcript and screenshot are retained as
  `web-chat/native-files-writer-metadata-visible-transcript.txt` and
  `web-chat/native-files-writer-metadata-result.png`.
- The completed 0.12.0 source-only increment implements an explicit provided-host mode,
  compatible bounded Node 22 execution, and an explicitly selected pdflatex
  converter for hosts that already supply the dependencies. This work does not
  solve ordinary Chat's package delivery by itself and is not installed in the
  frozen 0.11.0 plugin. Its completion and actual test results are recorded
  separately from that release's successful Windows/Cloud evidence.
- Native macOS tests and a dedicated CI job were added for Apple Silicon
  (`macos-14`) and Intel (`macos-15-intel`). These began as local source changes;
  the first remote attempt described below failed during private preparation.

- Provided-host preparation/conversion and identity checks passed 60 tests.
  Shared controller/workflow and explicit probe selection checks passed 78 tests.
  Actual Windows Node 24 checks passed 141 tests with two native Mac-only skips;
  a separate actual Windows Node 22.16.0 suite passed 15 tests. These are Windows
  results, not actual ordinary Chat or Mac execution evidence.
- The exact source-only 0.12.0 preview ZIP has 46 entries, 41 inventory resources
  and 22 core files. Size is 1363803 bytes, SHA256
  `385936e25fd8a0f644d04953990500d10daadcd5787cb7403428a05efa080f70`,
  inventory SHA256
  `ccc17c574722282411dea2a401ccdc73241b5956e2320a0ce214176b1f1ad896`.
  All entries passed CRC and byte comparison to the staged source; frozen
  0.11.0 ZIP remains unchanged. That exact initial preview was not installed or
  published.
- Three commands from that exact preview actually exited zero: provided
  preparation using existing Windows Python 3.12.14, Node 22.16.0, Pandoc 3.9 and
  Typst 0.15; trusted runtime extraction; then the schema-2 exact launcher and
  fresh bounded Wasm readiness. Preparation downloaded and installed nothing;
  converter outputs were reopened, and readiness confirmed cleanup. The local
  verification harness initially expected an outer `ok` field in the third
  command's flat environment result and raised KeyError after successful
  execution. Read-only receipt validation corrected that interpretation without
  rerunning any command. Receipt is `provided-host/actual-source-012/verification.json`,
  SHA256 `4bca765e7063407f21fc1c99124dac24c693674aaece209f3d97fa03e067c83e`.
- Ordinary Chat's existing native converter passed a separate fixed-input
  diagnostic with no package code, dependency installation or network requests:
  PNG 300x200, Pandoc 3.1.11.1, preserved pdflatex alias, two successful
  no-shell-escape passes, strict PDF reopening (one page and image), DOCX reopening
  and TeX existence. This does not test the new production converter or controller.
  The container interface returned combined output; retained stdout-labelled logs
  explicitly say separate stderr was unavailable. Original evidence ZIP is
  107041 bytes, SHA256
  `2d298000b0b23f0a377a517ad2ed61d603c1118e4aba464d566b222b9a0c23c8`,
  downloaded and CRC-verified under `web-chat/`. Complete package delivery,
  preparation, readiness and research flags remain false for this diagnostic.
- Independent native converter evidence review passed all 32 tracked member
  hashes, original PDF/DOCX embedded images and fixed body checks. Native binary
  before/after equality is retained remote metadata; the binaries themselves were
  not included for local rehashing. Review receipt is
  `web-chat/read-only/provided-converter-preflight-001-review.json`, SHA256
  `421335204d2911bcc3128d64f470ab3b1c74e1fc40cfbedf70ff80526e33867d`.
  The primary reviewer separately rendered and inspected the original one-page
  diagnostic, with no clipping or missing glyphs. Visual receipt SHA256 is
  `2cdac821aa77b4e462a3276de258f7d3088b9c7d3ac37e91f9ec03f94ad43b03`.
- Ordinary Chat's actual tool metadata exposes callable
  `mcp__GitHub__download_workflow_artifact` with `repo_full_name`, `artifact_id`
  and optional `file_name`, returning `result.file_uri` with a reusable connector
  file ID. Native `files__materialize` explicitly accepts connector-backed file
  IDs. This establishes a documented candidate contract, not actual transfer.
  Tool interoperability, a real artifact and automatic installed-package delivery
  remain to be tested. No GitHub access or permission change occurred in that
  metadata check; a following bounded read-only lookup is limited to the user's
  public `andongmin94/paper-factory` project.
- That following lookup returned the original normal JSON
  `{"total_count":0,"workflow_runs":[]}` for completed runs (limit five).
  No actual run ID was available, so no artifact listing or download was called.
  This bounded empty result is not proof that every artifact type is absent.
  Transcript and screenshot are retained under
  `web-chat/github-artifact-existing-run-lookup-*`.
- Independent exact 0.12.0 preview review passed 101 read/hash/reopen checks:
  46 ZIP entries, 41 inventory resources, 53 pinned runtime assets, 545 observed
  module/native files, original three command streams, converter outputs and
  the empty owned-worker journal. No native command or study was rerun.
  Review receipt is `provided-host/independent-source-012-review.json`, SHA256
  `d3c07cf2a922c3a4f31271e792744e607c1df487ed02bd0de238ea7f955ece3c`.
- The native CI increment was first validated locally: `scripts/ci_verify_plugin.py`
  and `.github/workflows/plugin-verification.yml`. It enforces actual arm64 and
  x86_64 macOS hosts, builds the original plugin, runs private preparation and
  the exact launcher/readiness with an empty owned journal, then requires the
  two actual native Mac tests and real PDF/DOCX tests to pass without skipping.
  Original bounded command streams, JUnit, converter outputs and the owned
  journal are retained by an explicit whitelist; runtime binaries, caches,
  environment files and private research inputs are excluded. A failed run
  retains diagnostics but never emits a successful distribution artifact.
  The duplicate Mac job was removed from `tests.yml`; Linux/Windows shards remain.
- This increment passed AST/YAML/CLI-help checks and independent 20-item static
  review with both reported evidence-retention issues resolved. Review receipt
  is `provided-host/independent-ci-verification-review.json`, SHA256
  `9ed81e935a0e120e79a7641bff97ce646b234a9ca56d6fa6665fc1cacde3617a`.
  Harness SHA256 is
  `caf0faab18a0b72ad1bf4be31921508623b2a1feaf311ca8fb2e8028a3e29b2c`;
  workflow SHA256 is
  `969e7a27adccc7a82089c317a15a521f4ded5909a093bd41084c8b8cf9c11b4c`.
  No actual CI/native preparation/test/dispatch/upload was run by that review.
- The user approved public verification-branch publication. The prepared source
  was pushed to `andongmin94/paper-factory`, branch `codex/plugin-portability-012`,
  at commit `5b213385a6e7ca597b48cc8f7f495acb5c697ee9`, parent
  `7b354faeed0adc9589327f04ad16829c22911e7c`. Main remains unchanged; no PR merge
  or OpenAI directory publication occurred.
- Actual Plugin verification run `37180608193`, attempt 1, executed both macOS
  architecture jobs. Apple Silicon and Intel private preparation failed; their
  diagnostic artifacts were retained and no successful distribution artifact
  was produced. Prior Windows and Cloud proof remains preserved. The overall
  goal stays active; successful Mac execution, ordinary Chat complete delivery
  and a verified ordinary Chat paper export remain required.
- The actual local Codex-installed 0.11.0 cache has 41 resources and 22 core
  files byte-identical to the frozen ZIP. Reusing its already verified private
  preparation required no dependency download or installation. The first exact
  launcher command returned `ready: false`: the default tool sandbox denied
  opening the supervisor lock (errno 13), before any guest was started. The
  frozen response incorrectly described this as busy and reported confirmed
  cleanup; neither field was accepted as successful readiness.
- A narrow approved host-tool invocation of that same installed launcher, data,
  environment and runtime returned `ready: true`, Node 24.21.0 and confirmed
  cleanup. Read-only inspection confirmed an empty owned-worker journal. No ACL,
  original journal or frozen package was changed. This proves installed Codex
  readiness on the observed Windows host with those permissions, not unrestricted
  default execution, a new study, macOS or ordinary Chat support. Independent
  13-check review receipt is
  `provided-host/independent-installed-codex-011-review.json`, SHA256
  `398a98b12196b9ebf869c87bf943ce6ed1b73982088ab0e130dfe7013630ae42`.
- Current 0.12.0 runner source separates unavailable supervisor files, a real
  competing owner and invalid retained state. Cleanup remains unconfirmed when
  supervisor preparation cannot be verified. Only an actual missing journal is
  treated as empty; unreadable and invalid journals block execution. Seventeen
  focused failure/cleanup tests passed, followed by two actual Windows Node
  22.16.0 readiness/TypeScript checks. The earlier preview, installed 0.11.0 and
  their original receipts remain unchanged; they do not contain this correction.
- The shared lease helper now converts only documented nonblocking contention
  into a busy result: Windows EACCES and POSIX EAGAIN/EWOULDBLOCK. Other native
  locking errors retain their original OSError. The JSON environment command
  preserves the three supervisor failure codes with bounded, allowlisted
  diagnostics and specific instructions; known unresolved workers still take
  priority. Thirty-two focused runner/controller tests passed. A separate
  workspace/workflow regression passed all 88 tests with no skips and unchanged
  before/after source hashes. Receipts are
  `provided-host/controller-locking-focused-001/receipt.json`, SHA256
  `4fc03b04047e1ac85be2ac5e1fedf90b51399e12ab3c0c3d1beb56b2fd5e2bf7`,
  and `provided-host/status-shared-regression-001/receipt.json`, SHA256
  `abe740f3b65d7af06d5b510ad363a7c3d89123b6059d938503f175bac72a3f3c`.
- A separate corrected 0.12.0 preview contains exactly those three changed core
  files, the updated package guide and regenerated inventory; other members
  match the first preview. All 46 entries passed CRC and exact byte checks.
  ZIP size is 1367184 bytes, SHA256
  `20d41e468d4cc71b24c8af38a06521f6d6017e6d241caaea6381ad6e7892a962`,
  inventory SHA256
  `688fb143de322060d685369ce90683b078e456e4cf2214bc798b977ce9e3fe9c`.
  Build record is `provided-host/package-preview-0.12.0-status-002/preview-build-report.json`.
  That exact ZIP remains a local snapshot; frozen releases were not rebuilt.
  Its separately named private installation is recorded below.
- This corrected preview's exact launcher reused the first 0.12.0 schema-2
  preparation, runtime and controller/supervisor namespace. Under default tool
  permissions it exited 1 with INPUT_UNAVAILABLE; that original failure is
  retained and did not claim ready or confirmed cleanup. Under narrowly approved
  host-tool execution, the same argv exited zero with ready, QuickJS, Node
  22.16.0 and confirmed cleanup. Receipts and separate original streams are in
  `provided-host/actual-status-source-012-002/`. No preparation, installation,
  dependency download, new study, ACL change or replacement data directory was
  used. This is actual Windows readiness with the observed permissions, not
  default unattended execution, Mac or ordinary Chat proof.
- Independent corrected-preview review passed 17 checks, including exact current
  builder inputs, all ZIP/inventory/core resources, 53 runtime files, 545
  prepared module files, original command streams and the same empty retained
  owned-worker journal. The reviewer used narrow read-only permission for that
  exact original journal after preserving default EACCES; no command was rerun.
  Receipt is `provided-host/independent-status-preview-review.json`, SHA256
  `71883d474e1eb403f6e069bc4fb506fe7a1bcf8f1f1a26cae28be3f11ccf3a12`.
- Independent source-correction review passed 13 checks with no remaining issues.
  The production AST changes are limited to journal loading, runner status,
  native lease error classification and the JSON environment response. Current
  source/test bytes match the retained before/after test receipts, and the worker
  and frozen ZIP remain unchanged. Review is
  `provided-host/independent-status-correction-review.json`, SHA256
  `ec520b1accd7a01398ec2d82375dea8019ab0ad772012d7ef8e2638290f0ec06`.
- A local source publication candidate is kept separately from plugin releases.
  Its exact selected source bytes, tracked deletions, declared-input coverage
  and excluded private files are recorded under
  `provided-host/publication-candidate-002/manifest.json`. It preserves the source
  reviewed before the approved public branch push; the candidate archive itself
  is not a plugin release, remote artifact or evidence of successful CI execution.
- The corrected preview was copied to a separate private plugin named
  `paper-factory-preview-012`, version `0.12.0`. Only root `plugin.json` name bytes
  changed; the 41-resource/22-core inventory remains SHA256
  `688fb143de322060d685369ce90683b078e456e4cf2214bc798b977ce9e3fe9c`.
  This private ZIP is 1365834 bytes, SHA256
  `8672a8e26766025b25f82960cdb4afd6d03f7432c63f1b99035a3e7682d2e92c`.
  Its upload and installation succeeded; the working 0.11.0 installation remains
  preserved. Local records are `web-chat/private-preview-012-installation.json`
  and `web-chat/private-preview-012-installed.png`. Its actual Work Cloud
  preparation/conversion/readiness regression completed; the original proof and
  its precise scope are recorded at the checkpoint below.

### Checkpoint recorded 2026-10-04T06:07:58Z

- The separate installed private 0.12.0 preview passed actual Work Cloud private
  preparation, controller import, fixed PNG/PDF/DOCX/TeX conversion and fresh
  QuickJS readiness with confirmed cleanup and an empty owned-worker journal.
  Independent review passed 25 original-byte/receipt checks; no scientific study
  was rerun. Original evidence is
  `web-chat/paper-factory-preview-012-work-cloud-regression-evidence.zip`,
  2302162 bytes, SHA256
  `1d5569d40002c2325e7d6cb22c5003778d1edce7dc79fd0bb86f0445a298533f`.
  Review is `web-chat/independent-cloud-012-review.json`, SHA256
  `1cb1644cd7af5055fd2820fb4165a59d73f3c79661769e599e809422a232f224`.
  This validates the 41-resource installed preview; it does not validate later
  Mac preparation source changes, ordinary Chat execution or a new study.
- Ordinary Chat's native `mcp__GitHub__download_workflow_artifact` response supplied
  the actual file ID used by `files__materialize`. The original ARM Mac failed-CI
  diagnostic reached its script container unchanged: 13774 bytes, SHA256
  `381bba9a844da1cac2c812ec30de239fdb4bc4313fef899e9399bb40ca6f65b3`.
  Independent inspection verified CRC, all eight members and their raw streams.
  The pilot evidence ZIP is 32174 bytes, SHA256
  `d4b5416de226770f0b96d43b3fb6900fffffa76ca0595540cf78fe5f09b3f07f`.
  Review is `web-chat/broker-pilot-independent-review.json`, SHA256
  `5dc40c54c2286dac807042c16e7a2ae06a8d4410e7127bfd028a1b2e9de3d454`.
  This proves an existing diagnostic artifact transfer; complete plugin delivery,
  host preparation, package execution and a study in ordinary Chat remain false.
  Signed URLs and opaque connector file IDs are omitted from the review.
- The retained ARM Mac first failure was private preparation command 2, exit 2,
  stage `dependency-download`, current artifact
  `pypandoc_binary-1.17-py3-none-macosx_11_0_arm64.whl`. Its original stdout is
  12134 bytes and stderr is empty. The safe report records `ValueError` without
  its underlying validation guard; no more specific cause is claimed from that
  diagnostic alone. The original failed artifact remains preserved.
- Current source omits `pypandoc-binary` from the six Mac wheel profiles and
  selects two pinned official Pandoc 3.9 Mac ZIPs with separately retained upstream
  notices. Windows/Linux wheel closures remain unchanged. These source and ZIP
  checks are not a second actual Mac CI preparation, runtime or research result.
- Current host packaging tests no longer read the obsolete Cloud dependency
  manifest or lock. A clean minimal fixture containing only the test, three
  current helpers, host manifest and eight pinned wheels passed 18 tests with
  real HTTPX/SOCKS construction, network forbidden and schema-2 preparation
  contracts checked. Source before/after matched. The initial test-port failure
  remains retained; the corrected run is
  `provided-host/cloud-packaging-current-fixture-002/receipt.json`, SHA256
  `5504e3acaaa58d7e1b94d7630acd089d6211f022c6f4b372c76542f9dca3f2d9`.
  Simulated host preparation and marker checks do not establish actual Mac support.

### Preparation redirect checkpoint recorded 2026-10-04T06:16:42Z

- The latest preparation helper uses bounded manual redirects with implicit client
  redirects disabled. Its exact source snapshot is 35303 bytes, SHA256
  `754f64d5ea978c01db67f6de8244c6c969e4891f2865d4a202851957fd5fc3bb`.
  Eleven focused tests passed with original stdout/stderr hashes and unchanged
  source. Receipt is
  `mac-ci-independent/source-fix-checks-003-approved/pytest-receipt.json`, SHA256
  `0cdeb2f6d176cf95b1b6cb87580ccfd59b15061cec170c4bb987287c3aad0325`.
- The two original Pandoc 3.9 Mac archives passed extraction checks, including
  pinned binary identities and the separately retained upstream notices; no
  foreign binary was executed. The extraction record is
  `mac-ci-independent/source-fix-checks-003-approved/original-assets-extraction.json`,
  SHA256 `df4b7751fc7eeccdcb49760e0f0e56704f499901b0596f0c3ffc3d532e5e60e7`.
  These checks are source/asset evidence, not actual Mac preparation or readiness.
- A fresh current-only fixture bound to that latest helper passed the same 18
  host packaging tests, including actual pinned HTTPX/SOCKS client construction
  with network forbidden. Its 13 source inputs remained byte-identical. Receipt
  is `provided-host/cloud-packaging-current-fixture-003/receipt.json`, SHA256
  `402631d5d7d177335b644df4a3d7d97905957651012ca0e7a735b7b527f9888a`.
  The earlier fixture002 and its pre-redirect helper proof remain preserved.
- Source-fix preview003's actual Windows launcher exited zero with flat
  `ready: true`, QuickJS, Node 22.16.0 and confirmed cleanup, using the existing
  schema-2 preparation, runtime and controller namespace. The original verifier
  incorrectly looked for a nested runtime result; its failure is retained.
  Read-only parsing of the original 665-byte stdout corrected that interpretation
  without rerunning the command. The empty journal remained byte-identical.
  Verification is `provided-host/actual-source-fix-012-003/verification.json`,
  SHA256 `a22076b27107402f1baa37944322e3199841e3556d3b69038d118feddd62a80e`.
  This 48-member/43-resource snapshot contains the earlier preparation helper,
  which was not executed by the readiness check. It does not validate the latest
  redirect preparation behavior, an installation, Mac execution, ordinary Chat
  execution or a new study. A new actual Mac CI result remains required.
- The final source-fix preview004 was packaged after the current README and
  plugin guide updates: 48 archive members, 43 resources and 22 controller core
  files, 1377658 bytes, SHA256
  `cfe4feac6d92e2cb7140ef2963933efce49a7659e7098ed8543ed7c8bc5fb86f`.
  Inventory SHA256 is
  `035e2049acd609a5184cbb8b36184c904e4fb2fb465b05ed59de8dc24591eede`.
  The archive CRC and latest preparation-helper bytes were checked against its
  build report, `mac-ci-independent/source-fix-preview-004/preview-build-report.json`.
  This is a source-only package: it has not been installed or used for a native
  Mac or ordinary Chat execution test. The Windows preview003 proof above stays
  bound to its earlier snapshot.

### Actual native regression checkpoint recorded 2026-10-04T06:45:06Z

- The corrected source commit is
  `7b72f5847dd1c270ea5c1ed2e8bedc75cb29ac05` on the separate approved branch.
  Plugin verification run `37182911973`, attempt 1, reached
  `native-regression-suites` on both real Mac architectures and failed there.
  Neither job retained a successful distribution. The original first preparation
  failures and this new failure remain separate evidence.
- The ARM diagnostic artifact `11296335405` reached ordinary Chat through the
  actual GitHub connector and native Files. Its original 117178 bytes, SHA256
  `b4fb6c696f2cb9a00b710614466c8a551901a9b3fa4cb6e97b9a82205e222352`,
  match the GitHub digest. The evidence ZIP is 241018 bytes, SHA256
  `64a434143983226eb31163afd0765361ccfbb00c07db18e3a7d59b7703930fc3`.
  The original archive has 25 members; the Chat narrative's count of 24 was a
  reporting error, not a changed archive. Raw member inventory is authoritative.
- Original command receipts show build, private preparation, runtime extraction
  and launcher environment exited zero; pytest exited one. ARM preparation
  verified 43 resources and actual native Pandoc/Typst diagnostics. Fresh
  QuickJS readiness reports Node 24.21.0 and confirmed cleanup. The retained
  empty journal is separate from the native regression result.
- The actual ARM suite recorded 250 passed, eight failed and two skipped.
  The eight failures are in Linux/Windows ownership fixtures that changed
  `module.os` while leaving `module.sys.platform` as `darwin`. A coherent local
  platform mock is required; assertions and actual Mac ownership tests are not
  removed or weakened. No individual successful native case is reconstructed
  from the quiet output.
- `native-tests.xml` was not retained: the report records a secondary
  `ValueError`. Collection reproduced two credential-shaped fixture URLs in
  automatic test IDs rejected by the unchanged log guard. Explicit semantic
  case labels preserve the fixture values and assertions; all 260 collected
  IDs then passed that guard. This is a reproduced sufficient cause, not a
  claim that the absent original XML proves its unique cause.
- Ordinary Chat also has actual supplied Python 3.13.5, Node 22.16.0 and ten
  required imported modules. The 3936-byte original capability JSON has SHA256
  `466786e3d7ac60c66c0f2531b03c0d3c3edfb30cb048a604830cdab3415e811a`.
  Full plugin delivery, preparation, readiness and research there remain pending.
- General Tests run `37182911833` ended with six successful and two failed
  jobs. The previous clone, OS mock and literature-link defects passed on actual
  Linux and Windows. Eight existing native AppContainer failures remain;
  the vetted case reports unconfirmed private-DACL staging cleanup. They are
  not hidden, skipped or classified as QuickJS failures.

### Original Mac byte verification checkpoint recorded 2026-10-04T07:40:44Z

- The approved verification branch subsequently reached source HEAD
  `68cb8e2463a1ddb715ff4d12f2c6ede1c2d45307`. Actual Plugin verification run
  `37184571428`, attempt 1, completed successfully on ARM and Intel. Earlier
  preparation failures, inconsistent-platform-fixture failures, missing JUnit
  evidence and their original artifacts remain preserved above.
- Both actual hosts were Darwin CPython 3.12.10, using private profiles
  `macos-arm64-cp312` and `macos-x86_64-cp312`. Preparation verified 43 resources
  and 22 controller core files, imported the controller and selected private
  Node 24.21.0, official native Pandoc 3.9 and Typst 0.15.0. The five original CI
  command receipts per architecture all exited zero; their original stdout and
  stderr byte sizes and SHA256 digests were independently verified. Readiness
  confirmed QuickJS cleanup, and both original owned-worker journals were empty.
- Each original `native-tests.xml` contains 260 cases: 258 passed, two
  Windows-only native cases skipped, and zero failures or errors. All five
  mandatory individual cases passed on each Mac: normal guardian completion,
  controller-crash EOF cleanup/recovery, complete PDF title, and both `[False]`
  and `[True]` native DOCX setting cases. The four required base names are
  `test_macos_guardian_normal_guest_has_actual_bound_completion`,
  `test_macos_controller_crash_eof_reaps_owned_worker_and_recovers`,
  `test_pdf_export_keeps_complete_long_title_in_one_typst_heading`, and
  `test_docx_export_uses_native_line_and_page_settings`.
- Both original diagnostic archives contain all six actual converter files:
  Markdown, Typst, PDF, DOCX, TeX and PNG. Independent reopening verified the
  21695-byte one-page diagnostic PDF, 21836-byte DOCX with one image and one
  table, 3096-byte TeX with image/table bindings, and 9699-byte 300x200 PNG.
  Original conversion receipts bind input/output digests and the selected
  private Pandoc command. These are converter diagnostics, not Mac research
  papers. Native executable/module identities are captured in the preparation
  receipts; those native binary bodies are not included in the diagnostics.
- Original ARM successful distribution artifact `11296387270` is 1392387 bytes,
  SHA256 `f566a7f0614d11d5ee55046c9bfd3e047e13249254a1efb00d2646942400d336`.
  Its original nested plugin ZIP is 1378652 bytes, SHA256
  `aebaaffebb1126e03ee26321444e9f59c15386af0cbff8a2293c3562d1f3acf7`:
  48 members, 43 resources, 22 core files and inventory SHA256
  `035e2049acd609a5184cbb8b36184c904e4fb2fb465b05ed59de8dc24591eede`.
  Forty-six copied non-inventory files match the immutable HEAD bytes; the
  remaining `plugin.json` matches the builder's exact declared JSON
  serialization and pyproject version. All 47 declared source-input pins were
  also checked. Equality to the earlier local ZIP's timestamp-dependent digest
  is not required.
- ARM diagnostics artifact `11296402192` and Intel diagnostics artifact
  `11296976029` were received as original bytes and checked against their
  GitHub size/digests. The Intel successful distribution body was not received
  for this audit. Its own original diagnostic build receipt records plugin
  SHA256 `4c2779fad5f3052c9c609b2b8e088e84df4307a66af34624a61040b3fe3516ca`;
  this is not an independently rehashed Intel plugin ZIP or a claim that its
  digest equals ARM's.
- Independent original-byte review accepted with no issues. Report:
  `.paper-factory/portability-implementation/2026-10-04/mac-ci-independent/run-37184571428-attempt-1/original-byte-audit-001/independent-macos-original-byte-audit.json`,
  72451 bytes, SHA256
  `e8030b9d49f03a9d6fb5143be3f94ca4c85d5d2f4e60eeeb3a3df64b2a01c7c2`.
  Original nested artifacts and verified members were exclusively retained in
  that private audit directory. No foreign binary, test, scientific experiment
  or network request was executed by the reviewer; ordinary-host verification
  remains a separate review.
- The combined ordinary Chat create-stage evidence ZIP is 3300321 bytes,
  SHA256 `be5d834fe6fd99b4ac7984b3849c63d2030fa4dcee9384724848ac30f9e2d6cc`,
  retained as
  `web-chat/paper-factory-ordinary-full-001-create-evidence.zip`. Its actual
  receipts record successful package delivery, explicit provided-host
  preparation with Python 3.13.5, Node 22.16.0, Pandoc 3.1.11.1 and pdflatex,
  and readiness with confirmed cleanup. No dependency download, installation,
  new venv, Work, PC connection, Docker/WSL or system PATH change was used.
  Fresh `research-9704196954a3` reached `ready/created` with code, execution and
  draft attempts all zero. A subsequent plan-freeze request is pending; no
  experiment, manuscript submission, export or full-paper success is claimed
  at this checkpoint. The ordinary-host/source-create audit is separate from
  the accepted Mac byte audit above.

### Ordinary Chat code-freeze checkpoint recorded 2026-10-04T08:32:32Z

- Fresh `research-9704196954a3` subsequently reached `ready/code_ready` with
  `code_attempt=1`, `execution_attempt=0` and `draft_attempt=0`. The frozen plan,
  both generated modules, bundle and actual independent review were compared
  against the reviewer-preserved originals after submission. The recovery was
  read-only and recorded no mutation calls; its owned-worker journal was empty.
- The original recovery ZIP,
  `web-chat/paper-factory-code-freeze-recovery-001-evidence.zip`, is 103231 bytes,
  SHA256 `86b1a973579a92be604d0f582dcca196f4c90ce5cf0fbd2490c28200592213b2`.
  The fresh post-freeze comparison passed with no blocking discrepancies:
  `web-chat/ordinary-code-review-001/frozen-code-comparison.json`, SHA256
  `999bf29472112aae70521ceb38d9f3a98a44b0f2a72e9f2e01520e6eabe2d068`.
  This establishes frozen input identity, not successful execution or results.
- The independent scientific reviewer was external Codex. The inspected tool
  catalog in this ordinary Chat did not expose a native fresh scientific
  reviewer, subagent or delegated model call. The subsequent same-Chat Deep
  Research static-review test completed with the bounded outcome below;
  selecting that UI mode alone does not establish reviewer independence.
- At this code-freeze checkpoint no ordinary Chat experiment, manuscript
  submission or export was recorded.
  Literature collection is not complete. A full paper and single-conversation,
  fully automatic PC-free completion remain unproved; the goal stays active.

### Same-Chat native static-review checkpoint recorded 2026-10-04T08:44:00Z

- The Deep Research test completed in the same ordinary Chat without a Work
  handoff. Its report records complete input reading, source/protocol/code
  hash comparisons and static review. It returned `accepted=false` and
  explicitly refused to satisfy the fresh independent-review requirement:
  no separate native reviewer job ID or isolated new context was demonstrated.
  This is a bounded negative independence finding, not an observed source
  algorithm or experimental-control failure; the test performed no execution.
- The retained rendered report is
  `web-chat/ordinary-native-review-deep-research-rendered-review.json`,
  SHA256 `9e113336e0dbec427cafc3cd5b8c40308a50552486f34a5940f5d72eb4262064`.
  Its provenance is
  `web-chat/ordinary-native-review-deep-research-rendered-provenance.json`,
  SHA256 `2ca19645fb459c03f46c94c34082ce64fec030be177744c3eda3e059905b949e`.
  The rendered result, raw DOM and screenshot are also retained privately.
- External Codex remains the independent reviewer used for the frozen code.
  The completed native static review does not establish standalone,
  single-conversation PC-free full production. Reported subsequent run results
  await an independent original-byte audit and do not advance the verified
  code-freeze state above.

### Ordinary Chat run/literature audit checkpoint recorded 2026-10-04T09:22:55Z

- `research-9704196954a3` subsequently reached independently audited
  `ready/analyzed`: `code_attempt=1`, `execution_attempt=1`, `draft_attempt=0`,
  and `terminal_control_failure=false`. The one captured run and one captured
  literature collection completed; the later recovery commands were reads.
  All 34 complete retained command receipts exited zero with empty raw stderr.
  These receipts establish captured command coverage, not every remote action.
- The original recovery ZIP is
  `web-chat/paper-factory-run-literature-draft-recovery-001-evidence.zip`,
  410283 bytes, SHA256
  `7f24363cfe096c33fe550560c6c173e21d938ad687b9d0eab4d0e2c0eb62b575`.
  All 200 member CRCs and safe paths, and all 198 declared main inventory
  records passed. The inventory excludes itself and also omits
  `runtime/inventory.json`; that runtime inventory was separately verified
  against immutable SHA256
  `ab3b2f965197a33c3c58ee1ca26b75871e78e8b59e4f09fd24addd6d88d7e51a`.
- Independent raw evidence review accepted all 17 checks:
  `web-chat/ordinary-run-draft-independent-001/independent-run-literature-draft-review.json`,
  140068 bytes, SHA256
  `99fc9765a420d4b50503873ba358bb37c31a6ad256a3b2f991729783aaa52495`.
  It independently checked 36 complete input cells, 72 observations and all
  158 fixture records totaling 74160 bytes. Actual production gate receipts
  record 39 attempted and completed calls. Positive and aggregate two-case
  negative controls passed; final cleanup was true and the journal was empty.
  Compiled code and remote native executable bodies are not included in this
  archive; their retained receipt identities were checked without executing
  or re-transforming source.
- The chosen first-nonempty comparison policy disagreed with production in
  four of 36 cells; the reference disagreed in zero. The reference-minus-
  production paired mean was `-1/9`, median zero, sample standard deviation
  `0.3187276291558383`. These finite typed JSON results describe that comparison
  policy, not a repository defect, population inference, SemVer, installation
  behavior, performance or native TypeScript equivalence.
- The three retained literature records passed raw/text/metadata binding.
  Both TC39 sources are bounded native-tool section extraction/transcription,
  not original whole HTML or complete retrieval wire logs. Their excerpts
  passed whitespace-normalized containment under the controller contract;
  exact substring containment was false. The pinned production module was
  read completely. An earlier literature metadata fetch retained only argv,
  so its exit and timeout duration are not independently established; the
  later read-only recovery receipt is complete.
- A fresh draft exists but remains unsubmitted. Its first separate manuscript
  review requested exact fixture values, a concrete reproduction procedure,
  and a reader route to the literature manifest/citation metadata. Author
  revision and fresh re-review are the next steps, within the manuscript
  schema. No manuscript submission or export is claimed. The external Codex
  reviewer boundary and the negative same-context independence result above
  remain in force; standalone full production is still unproved.

### Ordinary Chat final export checkpoint recorded 2026-10-04T10:27:40Z

- The actual final state of `research-9704196954a3` is `completed/exported`,
  with `code_attempt=1`, `execution_attempt=1`, `draft_attempt=1` and
  `terminal_control_failure=false`. Cleanup remained true and the original
  owned-worker journal was empty. All 20 complete final command receipts exited
  zero with empty stderr and no timeout: exactly one manuscript submission and
  one export, with no second run or reanalysis command. Fifteen artifact-byte
  responses decoded to the registered original bytes.
- The original final evidence ZIP is
  `web-chat/paper-factory-manuscript-submit-export-001-evidence.zip`,
  2256714 bytes, SHA256
  `b0a604cc585d65cee1194fa35ddc8bf7433e5b9d9200a2e146a7f12b8f9c8e62`.
  All 139 safe member paths/CRCs and 137 main inventory records passed. The
  self-inventory and additionally unlisted package-authority inventory are
  explicit exceptions; the latter independently matches the original
  `035e2049acd609a5184cbb8b36184c904e4fb2fb465b05ed59de8dc24591eede` pin.
  The nested reproduction ZIP has 42 members and all 40 selected inventory
  records passed, with only its declared README/self-inventory exceptions.
- Independent final original-byte audit accepted with no issues and 16 checks:
  `web-chat/ordinary-export-independent-001/independent-final-export-review.json`,
  82685 bytes, SHA256
  `24db3a22e1291d58646fbb2ac1815ced807f0806b95221593ca50fa05cfa7dc0`.
  Frozen source files, protocol, both generated modules, code review, execution,
  runtime receipt, 72 raw observations, analysis and all literature remain
  byte-identical to the earlier run audit. Export's trusted data revalidation
  is distinct from repeating the guest experiment. The preserved local parser
  confusion treating Markdown as JSON changed no research state and is not a
  source/control failure.
- The actual external manuscript reviews 001 and 002 returned `accepted=false`
  with two and three issues respectively. Review 003 accepted the revised
  22946-byte draft, SHA256
  `9618d98687f4d97fc03108d2d76846751424b05fac2255aa77f416b589e3b1c0`,
  with no issues and 18 checks. Only manuscript prose changed between these
  revisions; no source, protocol, code, literature or observations changed.
  The original ScientificReview is
  `web-chat/ordinary-fresh-manuscript-review-003/scientific-review.json`,
  6108 bytes, SHA256
  `f6e472586fdb6d235a8d0159dfdf1755971acf1896da7545f5c5462881721687`.
  Its real external reviewer provenance is 30912 bytes, SHA256
  `a9d206fca4b0d76d6b7cf79f9b5697d30239c37eb1115d1aa91dd332495dd73e`,
  retained beside it as `review-provenance.json`. Actual submitted review and
  canonical/Markdown bindings match this approved draft and its evidence.
- The verified original files were copied without conversion or overwrite to
  `output/ordinary-chat-study/`; standalone files, decoded controller artifacts
  and corresponding reproduction members match exactly:

  | Output | Bytes | SHA256 |
  | --- | ---: | --- |
  | PDF | 150310 | `77e12c6638d9dff3a1847c4c4014ecbc194c4985992565d56f92545e9115d134` |
  | DOCX | 59952 | `59b5de5eb44778175111ccdb0e6c151a33de008b0a0cb4d190a486a3a8d3d478` |
  | TeX | 26960 | `13a20f60e8e0b42b2559d854615b2cd37de20072c646536bc6be662c7dc2f9a1` |
  | Markdown | 23218 | `ac04c6d658441d02fac77d251e047cb0d0f11a045d4f287d25b995aa37e6e372` |
  | Figure | 47409 | `5dc09bbf192b3eba638127c2c9aecede7c6279a76b7a0a7495180c2601024ea9` |
  | Reproduction ZIP | 382999 | `1bba2a77bb07b77619acfb964cb69140f7102d4af41f75d87f5c44cc5253e72b` |

- The original PDF reopened as six unencrypted pages. Root rendered and read
  every page at 115 dpi, checking title, paragraphs, tables, references and
  figure without clipping, overlaps or missing content. All-page visual QA
  accepted with no issues:
  `web-chat/ordinary-export-pdf-qa-001/all-page-visual-qa.json`, 4838 bytes,
  SHA256 `7b778da93c555f22c70144983dbb4c605c1521467fa888355ce2c40b713718be`.
  This author-review output does not establish journal submission, acceptance
  or a publication-ready bibliography.
- Actual converter receipts preserve the selected `/usr/bin/pdflatex` alias,
  `/usr/bin/pdftex` target and two successful `-no-shell-escape` passes, with
  frozen Markdown input and actual PDF output digests. Only 4000-character
  stdout tails accompany the declared full 6603/6318-byte stream hashes;
  complete stdout rehashing is not possible from this archive. Empty stderr
  hashes are independently reproducible. Remote executable bodies, compiled
  JavaScript and the intermediate PDF-engine TeX are not supplied; receipt
  consistency does not replace independently reading those absent bytes.

### Bounded compatibility criteria assessment

The required implementation/resource-delivery/compatible-execution/export
criteria now have retained evidence: frozen Cloud research and working
installations were preserved, Windows completed a fresh paper end-to-end,
both actual Mac architectures passed private preparation/conversion/native
lifecycle CI, and ordinary Chat received the verified original distribution,
prepared its existing host and completed a controlled study through verified
paper export. The one shared controller and evidence/export contract remain.
Final goal status and publication checks are recorded separately.

This ordinary Chat test used actual external fresh Codex code/manuscript reviews.
Its same-conversation Deep Research `accepted=false` remains a negative native
independence result, not a source/control failure. A standalone single-conversation,
fully automatic PC-free workflow is not established. Personal Mac plugin
installation, a Mac research paper, default unattended Windows tool permissions,
public-main merge, public-directory registration and upgrading the working
installation are separate, unverified scopes; this completion evidence does not
claim them or universal support for every account/host.

The tested execution/package source is commit
`68cb8e2463a1ddb715ff4d12f2c6ede1c2d45307` and its frozen CI artifact/inventory,
not a later documentation commit. README and plugin installation documentation
are ZIP-root inputs; subsequent approved edits to those two inputs do not mean
all 47 current source inputs still equal the tested archive. The remaining 45
inputs and 43 skill resources are unchanged, and no frozen package is rebuilt
by these documentation edits. The retained 0.10.2 release/research evidence and
working 0.11.0 installation remain separate and unchanged.

Separate general Tests run `37184571403` at that same source commit still has
one Windows native staging/private-DACL cleanup failure and seven legacy
WindowsRunner failures, preserved in
`mac-ci-independent/general-ci-37184571403-terminal-connector-record.json`;
these are distinct from successful Mac Plugin verification `37184571428`,
scientific controls and native-review independence, and no wholly green test
suite or new fallback/ACL repair is claimed.
