# Standalone app UI source

The desktop workspace uses genuine [neobrutal-ui](https://github.com/andongmin94/neobrutal-ui) source pinned to [`b4da2463fe710a77bf464c65125a1a7f40424722`](https://github.com/andongmin94/neobrutal-ui/tree/b4da2463fe710a77bf464c65125a1a7f40424722), inspected on 2026-10-05. The upstream README and installation guide support React 19 + Tailwind CSS 4 UI components in Vite. Next.js App Router page templates are not imported.

## Five-stage improvements: 0.13.1 verification (2026-10-06)

All five source improvements are implemented. Stage 1 limits Tailwind class scanning to renderer source and bundles the original Pretendard Variable WOFF2 and OFL. Stage 2 retains the work/account lock until owned experiment cleanup and pending inference/index writes are confirmed. Stage 3 makes window close and app quit share one cleanup task: failed shutdown keeps the window and evidence available for retry, and the Python IPC exits only after an acknowledged shutdown and actual process closure. Delayed replies and failed account-journal writes do not bypass these gates.

Stage 4 replaces the obsolete `workflow.resumeWriting` RPC with `workflow.resume`. Public metadata exposes `preparation`, `authoring` or null. The first two permit respectively the first experiment after verified preparation or writing from retained successful analysis. The engine verifies source/artifacts/protocol/approval and cleanup evidence again before appending an immutable resume receipt; main checks the fresh response before any account/model call. Ambiguous executions, pending cleanup and failed scientific controls expose no resume button. Neither restart nor resume clears a previously recorded dispatch marker.

Stage 5 removes `SaveArtifactDialog` and the renderer's destination-path argument. Main supplies native file/folder selection, holds a single save task across verification, the dialog and the commit, and waits for it before shutdown. PDF/DOCX/ZIP/validation JSON use a verified temporary file and atomic replacement. Markdown/TeX use a new folder containing unchanged manuscript bytes and all referenced frozen PNG bytes, published only after every write succeeds. Engine and main verify figure names, directory, size and SHA; the engine also checks manuscript references against the frozen inventory. Cancellation creates no output, and a failed commit preserves previous exports. No compatibility path for the removed dialog/RPC remains.

Final source checks used isolated homes and synthetic transports: **260 desktop/SDK passed, 1 Windows skip; 10 Electron passed (full suite 9 in 1.3 minutes, then one added native IPC case in 9.0 seconds); 856 Python passed, 7 skipped (251.44 seconds)**. Python covered native QuickJS, cancellation/shutdown deadlines, terminal-control preservation, preparation/authoring resumes, supporting-document behavior, and real Pandoc/Typst exports with frozen figures. Node regressions include commit failures that retain old bytes. Electron covers actual font loading, account/work gates, retryable close and the production native-save helper with mocked OS choices. The helper-based save fixture replaces main IPC; the additional native IPC case keeps every original main handler and the actual bundled engine. Logs are retained under ignored `.paper-factory/stage5-{node,electron,python-full}.log`. The earlier stage-specific subsets below overlap these checks and are not added to the final totals.

The additional native IPC case seeds only a new owned engine directory with one completed synthetic Workflow and frozen PDF/Markdown/TeX/PNG bytes. Only native dialogs are mocked. It verifies PDF selection cancellation, Markdown with its original PNG, and nine actual main lease rejections during a deferred save: sign-in, disconnect, profile/model changes, model verification, create/resume/revise and duplicate save. Concurrent window close and `app.quit()` wait for the native chooser; the selected PDF commits before actual engine shutdown and process closure. Source artifact bytes, the Workflow row and the launch-only connection journal remain unchanged. These fixture bytes are for saving, not document rendering or scientific evidence. This test skips only if runtime inventory is absent; it ran successfully against the built Windows runtime in this checkpoint.

The Windows runtime builder now extracts only the verified Node executable and license from the official ZIP; the unused npm tree had exceeded Windows path limits. The pinned host-dependency catalog SHA is updated to its tracked bytes, with the same Windows package inputs. The final bundled runtime has **4,463 files, 564,868,337 bytes** and inventory SHA256 `0330fbc474fb159212d20e64bc69f9ed3f8e60a482c4cf4665a07e7ff5cf8c1a`. Native Python/Node/QuickJS/Pandoc and PDF/DOCX/TeX diagnostics passed. The packaged IPC performed `runtime.status`, empty `workflow.list` and acknowledged `shutdown` twice in a separate temporary home; both processes exited 0, confirming restart after the first lease was released.

`desktop/release/standalone-package-verification.json` records ASAR's 7,667 members, current main/preload/renderer bytes, full engine-source equality, locally bundled Pretendard/OFL and every runtime file hash. Package verification never starts the installed application or signs in.

| Windows artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `Paper Factory Setup 0.13.1.exe` | 236,934,358 | `4f5a5177ef30597da26b9ddd32f77cee55d9fabb825832d0c9f8fde3f254ef36` |
| `win-unpacked/resources/app.asar` | 44,703,805 | `58d8269885b6a270e238633c20606ac17229fc23f11f4425255c3b882ffa5ba5` |
| `win-unpacked/Paper Factory.exe` | 245,726,208 | `3272c1d00da8540f042031f04ac5c960a116670c8db9c92b616bec79eee24afd` |

The 0.13.1 installer was built and its packaged contents verified; installation, live OAuth/inference, new papers and macOS packaging were not performed in this checkpoint. Existing authentication/research data was not accessed. Prior dated installation and research evidence below remains historical 0.13.0 evidence.

## Five-stage improvements: stage 2 source verification (2026-10-06)

Cancellation now waits for the owned Python workflow future outside the workflow locks, then verifies termination using the retained worker identity and hash-bound execution/cleanup receipts. A successful cancellation reply explicitly includes `cleanup_confirmed: true` and `cleanup_pending: false`. The planned worker wait and native stop share a 30-second budget; the main-process request uses a 45-second transport deadline. Unexpected OS, lock or I/O delays remain subject to that transport failure gate.

Main retains a durable per-job cleanup marker across model abort, transport failure, runtime refresh and restart. It releases the work/account lock only after verified cancellation and inference/index persistence. Index write failure still sends the engine stop request. Partial model bytes are retained and reconciled without overwriting conflicting evidence. Natural completion and failed scientific controls retain their authoritative states and artifacts. Missing worker identity and missing verified cleanup evidence keep the job locked rather than claiming termination.

`결과` exposes `정리 다시 확인` even without login or a ready runtime. Account selection and disconnection now publish explicit busy states; research and account changes have mutual guards. Startup restoration holds the same gate until stored metadata and the engine listing have been inspected. An invalid index remains preserved and locked.

Verification used isolated temporary homes and synthetic transports: **220 desktop/SDK passed, 1 skipped; 6 Electron passed (11.3 seconds); 171 workflow/IPC passed (68.65 seconds)**. Regressions cover delayed cleanup, negative/missing confirmation, persistence failure, exact interrupted bytes, multiple pending workflows, restart, startup races and completed-state preservation. Logs are retained locally under `.paper-factory/stage2-verification/`. No actual authentication, model inference or existing research was invoked. Installed-app delivery, shutdown handling, resume eligibility and native document save improvements are subsequent stages; prior dated installation/research evidence below remains historical.

## Imported files and responsibilities

| Upstream source | Desktop destination | Use |
| --- | --- | --- |
| `registry/src/components/ui/button.tsx` | `desktop/src/renderer/components/ui/button.tsx` | Base UI action button |
| `registry/src/components/ui/button-variants.ts` | `desktop/src/renderer/components/ui/button-variants.ts` | Upstream staged press, shadow, variant and size styles |
| `registry/src/components/ui/card.tsx` | `desktop/src/renderer/components/ui/card.tsx` | Connection, research and results containers |
| `registry/src/components/ui/badge.tsx` | `desktop/src/renderer/components/ui/badge.tsx` | Separate login and model response states |
| `registry/src/components/ui/select.tsx` | `desktop/src/renderer/components/ui/select.tsx` | Base UI account and available model selection |
| `registry/src/components/ui/checkbox.tsx` | `desktop/src/renderer/components/ui/checkbox.tsx` | User acknowledgement of official credit usage setting |
| `registry/src/lib/utils.ts` | `desktop/src/renderer/lib/utils.ts` | `cn` retained; unused upstream documentation naming helpers omitted |
| `registry/src/data/{colors,theme,theme-styles}.ts` | `desktop/src/renderer/neobrutal.css` | Exact output of upstream `serializeThemeCss()` with default Mono palette and settings |
| `LICENSE` | `desktop/third-party/neobrutal-ui/LICENSE` | Original MIT copyright and permission notice |

The component source files are copied without behavioral or styling changes. Git blob SHA256 values are recorded in `desktop/third-party/neobrutal-ui/provenance.json`, including upstream utility and theme inputs. The imported sources use the renderer's `@` alias. Application CSS adds layout, locally bundled Pretendard Variable, error/response containers and reduced-motion handling around these components.

The application stylesheet imports the original theme with `source(none)` and explicitly registers only `src/renderer/` for Tailwind class detection. Historical desktop output and runtime files are ignored local artifacts rather than UI sources. Their presence must not expand the renderer build's scan scope.

Pretendard Variable's full WOFF2 is bundled under `src/renderer/assets/fonts/` and loaded by application-owned `@font-face` CSS, with weights 45–920. Font source, version and SHA256 are recorded in `desktop/third-party/pretendard/provenance.json`, alongside the original SIL Open Font License. The renderer does not request a font from a CDN or require a system font installation. Package verification checks the CSS-referenced WOFF2 and license bytes; isolated Electron fixtures check actual font loading at body and heading weights.

The local reference checkout and one-time source preparation script are retained under ignored `.paper-factory/standalone-reference/`. They are development evidence, not runtime requirements. Consumers and installed applications need only the tracked renderer source, pinned desktop package lock, and license files.

## Dependencies

The minimal imported component set needs React 19, React DOM 19, `@base-ui/react`, `class-variance-authority`, `clsx`, `tailwind-merge`, and `lucide-react`. The generated base CSS imports `tailwindcss`, `tw-animate-css`, and `shadcn/tailwind.css`; Tailwind 4 is built through the Vite integration. Upstream source requirements at the pinned commit are `@base-ui/react ^1.8.0`, `class-variance-authority ^0.7.1`, `clsx ^2.1.1`, `tailwind-merge ^3.6.0`, `lucide-react ^1.24.0`, `tw-animate-css ^1.4.0`, `shadcn ^4.21.0`, and React/React DOM `19.2.8`. The desktop lockfile records resolved versions.

No Next.js, gallery, chart, dashboard, research page template, or documentation site code is included. The app composes the original components into connection, credit guidance and research forms with actual engine state and verified artifact actions. The credit checkbox confirms a user action; the account's remote setting is managed on the official usage page.

## Desktop workspace layout

The application layout now follows a VS Code-style workspace: a fixed left sidebar selects `연결`, `새 연구` or `결과`, with a compact top bar and a main viewport. The original neobrutal colors, component source, shadows and Base UI behavior remain in use; the workspace composition and responsive layout are application-owned CSS.

`연결` contains OAuth, available models, verification responses and credit guidance. `새 연구` contains a compact runtime status and the repository, goal, writer and reviewer form. `결과` contains saved jobs, their actual stages and errors, explicit cancellation/resume controls, and verified artifact save/open/folder actions. Each selected panel scrolls within its viewport instead of placing connection, research and results in one long document. The sidebar remains available while execution controls are disabled.

Eligible idle jobs also provide `추가 근거 선택` and a compact attached-document list. The renderer passes only the research ID to the native picker. Selected documents are preserved for the next writer/reviewer requests and reproducibility ZIP; importing them does not automatically resume research or invoke a model. The UI distinguishes the current import time from unverified claims of earlier activity inside the documents.

Panels remain mounted when hidden, preserving the repository, goal, writer and reviewer selections during navigation. Snapshot subscriptions and research state continue across panel switches. First entry selects `연결`; a connected account receives a clear next step into `새 연구`. Sidebar buttons expose tab selection and associated panels through accessible tab semantics, with Up/Down and Home/End keyboard navigation. At narrow widths, the sidebar contracts while retaining its navigation controls.

## Validation boundary

The screen reads sanitized snapshots and invokes only the explicit preload API. The renderer receives account display information, model identifiers, safe errors, and completed verification text. Authentication credentials remain in the Electron main process. A restored login never manufactures a model response; only a completed model verification is shown as a successful response.

Typecheck, renderer build, automated UI checks, actual sign-in/inference, app restart restoration, and Windows/macOS installation verification are distinct checks. Importing upstream source alone does not establish them.

The initial sidebar fixture checkpoint on 2026-10-05 completed with **4 passed in 14.3 seconds**. These Electron tests use separate temporary application data and explicitly synthetic IPC snapshots. They check navigation, preserved form/model selections and related UI behavior; they do not establish real OAuth, production model inference or completed research. The app and SDK test suites at that checkpoint separately reported **87 passed, 1 skipped**.

The root agent separately confirmed the new Windows installed application's GUI launch, restoration of the real ChatGPT connection and a newly completed model verification response at **2026-10-05 10:33:39.228 UTC**. This is actual installed-app evidence, distinct from the synthetic fixture suite. Its retained evidence directory is `.paper-factory/standalone-verification/installed-app-20261005/sidebar-install-ab3e1e10-c1cf-4246-80d0-2343765ac032/`.

That initial verified sidebar installation identifies its artifacts by SHA256:

| Artifact | SHA256 |
| --- | --- |
| Windows NSIS installer | `2e21ba2cb3de7361b9264235650b9d57793552b2662b0672c1f7593128dff8fe` |
| Installed application ASAR | `7316b0b4731ca0b977870f4ca2e6de0d51221043db0be218e4ca9a392e125b64` |

The Source8 supporting-import checkpoint reported **125 app/SDK tests passed, 1 skipped**, **4 Electron fixtures passed in 16.7 seconds**, and **756 Python tests passed, 7 skipped**. A regression demonstrated the supporting-document import's stale `busy=true` return before the fix and the released `busy=false` return after it. Its evidence is retained in `.paper-factory/standalone-verification/evidence-return-lease-20261005-c86ec677b92747c5b3814be040434628/`; the full Python run is in `.paper-factory/standalone-verification/supporting-import-full-20261005-2b032b42f8d34d338d0bb855888d2f38/`.

The root agent separately verified **Windows installation 8** on **2026-10-05 13:50:24.002–13:51:12.871 UTC, exit 0**. Its complete runtime comparison at **13:51:15.081 UTC** covered **4,463 files, 564,850,370 bytes and 22 engine source files (21 Python files and one worker)**. The real app restored its own ChatGPT connection and received a newly completed Astra verification response at **13:52:54 UTC**. Its artifacts are:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| Windows NSIS installer | 234,883,177 | `3da7d6e151dd51eec915a690fe28b8cd8a279c96e8b6494f106649373efcbff9` |
| Installed executable | 245,726,208 | `f764ac81998c73fdb55f63ce91f00c4e68a86cea909cb0709a78ff3b4a65c5b5` |
| Installed application ASAR | 42,628,437 | `66b2b1f00b57abe42e716d6cef1c49001efefa628e6923768688ba20d398dde8` |

In this actual installed UI, the previous five supporting documents (29,186 bytes) plus a pinned public commit API document (8,481 bytes) produced **six documents, 37,667 bytes**. The root confirmed that the import completed and execution controls became enabled, verifying the returned-busy fix independently of the synthetic tests. Native import evidence is retained in `.paper-factory/standalone-verification/evidence-return-install-a2101e4c-cd61-4b57-9583-09a50971e26e/`. A new writer/reviewer request is still pending; valid completed papers remain **0/3**. The earlier fifth-installation protocol-invalid report export is a separate historical result.

Current Windows, macOS ARM and macOS Intel runtime profiles passed static file comparisons. macOS native execution, DMG/CI verification and a clean environment without developer tools remain unverified, and the installer is unsigned.

These results record the observed UI, connection restoration and completed verification response. Manuscript/artifact validation and platform installation checks remain separate evidence categories documented with their own results in `docs/standalone-app-plan.md`.

## Source9 controller source QA — 2026-10-05 14:42 UTC

The Source9 checkpoint at **2026-10-05 14:42:30.692 UTC** passed **160 app/SDK tests (112 desktop + 48 SDK), 1 skipped**, including build/typecheck and 35 new regressions. Its four isolated Electron fixtures passed in **16.9 seconds** using temporary application data. The skipped SDK case is the existing Windows-inapplicable POSIX permissions/symlink test.

Planning now reads complete selected source, named consumers and available root README/license/NOTICE text before the model request. Every source page and the assembled UTF-8 SHA/byte size are checked; the cumulative 500,000-character material limit rejects partial delivery. Supplemental bytes retain their external-untrusted provenance. Cancellation holds the busy lease through model cleanup and authoritative engine-status reconciliation, then returns the final idle snapshot. Source metadata is validated inside main; the materials prompt carries complete selected text, rather than a separate full hash/size inventory array.

An independent read-only audit found no concrete blocker and matched both source snapshots against the final receipt: research.ts SHA256 `068932622aaeb9a91563cb45ccf13df2ab3e6d10c55c78675747f9c250d64a95` (36,534 bytes), research.test.mjs `b3a57e3896dbede8afe9cb7fac9f76df57a126d5825158c93b52f9311c31cd2d` (58,429 bytes). The final source/log receipt is `desktop/.paper-factory/standalone-verification/controller-source9-fix-6bb85d72-e958-4fac-a5a1-91f126de2d43/source-final.json` (SHA256 `97f70e4a92881eb1728b91a6952e6bee231da5826a5ff861becf4063430fc5d2`); the immutable independent comparison is `.paper-factory/standalone-verification/source9-readonly-audit-20261005-5c49f8d84f704d4c8b573f2324d52dc4/upstream-comparison-20261005-7acbc0fa76a942f4822b5028036d7d73/comparison-receipt.json`.

This is source and isolated-fixture QA. It does not establish installation 9 delivery, cancellation in the actual installed app, real authentication/model behavior, or a valid completed scientific paper.

## Source9 installed Windows checkpoint — 2026-10-05 14:53–14:58 UTC

The actual ninth NSIS installation ran at **14:53:20.143–14:54:11.817 UTC, exit 0**. The installed runtime comparison at **14:54:22.648 UTC** verified all **4,463 files and 22 engine sources**, with inventory SHA256 `a05e54466fd5a77f8f592154f441fd37e15d09266b59e4f8ac8d7c100d72a6e8`. The installed application comparison at **14:54:47.853 UTC** matched the built main/preload/renderer entries. These are later installed-app checks, separate from the Source9 source/fixture checkpoint above.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| NSIS installer | 234,883,742 | `7f47576e79d30957c71f7c14cc26ca8dbe9cc17a91919b79ee07ece05797705c` |
| Installed executable | 245,726,208 | `295d0a3b5f25f171f44d7fa6fe5cd7a312dc0866d8e7ab4307b1f18c773ed0c0` |
| Installed ASAR | 42,632,122 | `3d16c8956f29c94be4c40a2de811a02772447a0dfd04399591a42ba0ceb073e0` |

The independent read-only audit rehashed these three complete files against the package/install receipts. The executable remains **NotSigned**. The restored app's own connection received a new completed `gpt-6-astra` verification at **14:55:56.029 UTC** (safe event recorded at 14:55:56.030), text SHA256 `a0ae5d7b5f387303253b02b254d91296c7d35747c075fd08cdfff9d1955ecbce`. Completion is established by the safe connection evidence and saved screen text; the saved connection image itself shows login/model selection with the response below its visible viewport.

The root then explicitly resumed and cancelled Frontron `research-b071d98fbed0` authoring. Request `ad3bafd7-33a4-4e54-8d83-85cda4675f25` started at **14:57:42.446 UTC** and was retained as **interrupted at 14:57:52.850**, including 857 partial characters. The backend cancellation record updated at **14:57:52.914851 UTC**; the later app job projection at **14:58:34.588** matches `paused / analyzed / cancelled / CANCELLED`. The native screenshot shows the same engine state and the idle readiness label. This interrupted request has no completed outcome or newly approved manuscript.

A live-WAL-aware SQLite `mode=ro` audit confirmed all **102 previously frozen artifacts** retained their original path, SHA256, size and full bytes. The scientific execution remains attempt **1**, **17 production calls**, **32 raw observations**, and confirmed cleanup; raw SHA256 is `5df31089d6aaae47376db7424086246edb318e98e3339de18e61638481919657`. Raw/protocol/control links in the existing analysis remain consistent. No experiment was rerun, and this retention/state check does not adjudicate scientific validity or contribute a successful paper.

Installation/UI evidence is retained in `.paper-factory/standalone-verification/planning-material-install-e96560c6-5b66-460c-abde-e917ff0589de/`. The independent audit is `.paper-factory/standalone-verification/source9-installed-cancel-audit-20261006-86e190df779a4d48a0f27f091f9175dc/readonly-actual-cancel-audit.json` (SHA256 `92be1e201f0d0a78ff43f09b8f23eb46d25f52be9a79e154ecf0015a4014f169`), with `crossreceipt-verification.json` (SHA256 `58dfe8755f2ee554493a3515aa21dad82818f367944deca9fa71f71458c7ceac`). Earlier dated evidence and the macOS native-validation limitations remain unchanged.

## Source11 actual saves and Source12 installed checkpoint — 2026-10-06

Source11 replaced the native SaveDialog with an existing Base UI dialog for an absolute destination, Save, Cancel and correctable errors. Main retains trusted-frame/busy/artifact digest checks, protected app-data destinations, real writes/fsync and post-write digest validation. This did not change the original neobrutal-ui components or add dependencies. Source11's nine final frontend source/test files are preserved byte-for-byte after Source12; the original final receipt is `f165d3a5c7212497233a76b0c9636f9ed46f940838b68835463fce93eeba6d66`. Actual Source11 DOM controls saved all five final Premiere artifacts and all five navigation artifacts. Their exact frozen size/SHA matches, PDF ten-page visual QA, DOCX body and ZIP inventory checks are documented in [the dated verification record](standalone-verification.md). Both studies count toward **2/3** valid final papers; the old preview/SemVer reports remain excluded.

Playwright controls the installed Electron renderer and captures Chromium output without OS screen capture or native coordinate input. The PDF Open buttons completed unmocked shell requests; the native Reader accessibility tree did not expose full document paths or rendered content, so exact Reader rendering is not asserted. Separate existing Chrome154 sessions displayed each exact user-saved PDF URL and first page. Unmocked folder buttons were followed by read-only Explorer accessibility showing the complete study/export path and20 filenames. No native activation, input or screenshot was used. Physical monitor power state was not independently measured.

Source12 changes only `desktop/src/main/research.ts` (39,851 bytes/SHA256 `c29d8f1ed358fec05ab2fbf80e9c725f571b852d17ed47b0f5b0ff7060c15949`) and `desktop/tests/research.test.mjs` (76,833 bytes/`94f4fb89ce27e733c9f95fdfb8822a0ebbf56311500dd3d0e02eed045ea33cf1`). Complete manifest-verified root README and nested LICENSE/LICENCE/COPYING/NOTICE originals now reach every plan/code/manuscript author and fresh reviewer. A controller descriptor outside the untrusted JSON explains original-source retention and successful ZIP contents, without declaring a future export, license permission or review approval. Existing source paths, paging, UTF-8 byte sizes/SHA,500k fail-closed cap and review acceptance conditions are unchanged.

The pre-fix three-stage delivery regression failed; the19 new regressions then passed. Full npm tests passed **203 (155 desktop+48 SDK),1 existing Windows POSIX skip**, and four isolated Electron fixtures passed in **20.2 seconds**. Source22 and all nine Source11 frontend files remained unchanged. Final source receipt `f72b3de43e70d2edeb43f4a6a04e41bff4e53b6d56d04d8d904ffbc2e207d2fa` is in `.paper-factory/standalone-verification/source12-material-notices-548bde9a-5d7f-4a73-b0a8-613bdb8a8662/`. Independent read-only audit `c7b0d31cf70dc33f222234499755c7d50e5153914b6affa966702a35c73c956c` found no blocker. These tests are synthetic/source checks, separate from actual research.

The actual twelfth NSIS installation ran **18:47:10.578–18:47:57.230 UTC, exit0**. At18:48:13.263 the EXE, ASAR, built main/preload/renderer and all referenced assets matched; at18:48:14.372 the complete4463-file runtime and22 engine sources matched. Source12 frontend changes required no new Python test run or runtime rebuild: the exact Source11 Python794/7skip and Windows/Mac runtime/QA evidence is retained. Current inventory hashes remain Windows `476a0042d48f5c120b6e06e54cc388dbc8773dfa70229c645c2fb51099e894ce`, Mac ARM `9ed9b00611c1e40e1c1377a67ac85059d5a6678f54706ff0c86c7de445eabee7`, Intel `2b51e6b6d35d048061ad7fe8fe3722ef086db2635c4154fb056946db519904ed`.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| Source12 NSIS installer | 234,889,236 | `126c5c2bc31c7944d4950de06b11efffebd233cc67af2c9677391d00e0715fac` |
| Installed executable | 245,726,208 | `d2063b8b4e0bf834f16edd0b918a1a3ee9a8b3b74c93d8bef0115c02b98bcd7c` |
| Installed ASAR | 42,653,282 | `fc0685589d439039d63375293f5193890be83986c2dc575964a35f912b485428` |

The installed app was launched through Playwright's Electron API with `isPackaged=true`, the exact installed ASAR and the same own userData. Its restored connection refreshed the actual five-model server list and received a new completed Astra response at **18:49:12 UTC**, text `Paper Factory connection works.` No other application's authentication files were read or copied. Actual Astra writer/Sol reviewer selectors were checked before a single existing CLI resume button click at **18:51:09.603 UTC**. The CLI frozen plan/source and all46 pre-update artifacts are retained; the scientific experiment had not run before this resume. No manual diagnostic document was imported.

Source12 package/install/model/UI proof is `.paper-factory/standalone-verification/controller-provenance-install-source12-44bdf328-94c9-4a87-be54-97dd62fa1014/`, with static package receipt SHA256 `619e469ec9ae7a021de0207d1ab1eb362546a7c2dc89d33bf7c1cdf165adedb8`, installed app `39ab8aa33b0210cdc02ccb07f01354dd7888c5326f64ab05c4e43ae68d9781d3`, installed runtime `e97268ad0bd0c5f2a7963d96cbfd1f7d0c72856c1b61d91975ddcce4537976cc`. The EXE is NotSigned. A clean Windows VM and actual Mac native execution/POSIX modes/DMG/install/CI remain unverified. The scientific validity and final output of the resumed CLI study remain pending at this dated checkpoint.

## Final three studies and normal restart — 2026-10-06 04:20 KST

The final accepted study count is **3/3**: `research-a90ccd5fee76` (Premiere), `research-6561ac63db99` (navigation), and `research-f68ee0139f78` (Frontron CLI). Each used the actual installed application's own ChatGPT connection, Astra author and fresh Sol reviewer, and one successful scientific execution. Old preview/SemVer failures, code rejections and superseded manuscripts remain retained and excluded from the count. Current frozen artifact counts are124/72/112. Full scientific/model bindings and final file paths/SHA are in [the final verification record](standalone-verification.md); this count does not claim journal acceptance or research novelty.

The root operated the actual DOM controls for all **15 primary saves** (PDF/DOCX/Markdown/TeX/reproduction ZIP per study), and matched each complete saved file to its frozen size/SHA. Independent output QA directly viewed all **29 PDF pages** (10+10+9), read complete DOCX bodies (65/66/62 paragraphs, two tables and one figure each), checked all19 OOXML members per DOCX, and verified ZIP176/476/261 members by CRC, size, SHA and inventory. DOCX page-layout visual QA was not performed. Three existing `figure-1.png` files were separately delivered from the verified actual saved ZIPs to resolve Markdown/TeX relative references; the15 app-saved files and actual workflow/manuscript bytes remained unchanged. This is companion-file delivery, not an additional app Save action or a new measurement.

Each PDF Open button completed an unmocked shell request without an app error. Exact native Reader file paths/rendering were not exposed and are not asserted. Independent existing Chrome154 displayed the three exact user-saved PDF file URLs and first pages, with their complete file SHA checked. Each folder button was followed by read-only Explorer accessibility displaying the full corresponding research/export path and20 filenames. Native activation/input/screen capture remained zero. CLI actual UI save proof SHA256 is `1bef764fc729b3ea77361619d04126668ed04b8be43ad4bfc24b0c0baae7da50`; full saved-file comparison is `6882f090063722ede5a04f6cdf5761f611475bfcf3b13d8446e1a43db0700d58`. CLI Open/folder receipt is `e7222c8394893ee817f960ba8cd2d9144f206033e331d2d6730f4f0d40378dbe`, with subsequent direct Chrome visual proof `b37a7a68b14ce49b4d8a282a848ab73b664905dcd52312c99b512ad4919a2ad5`; the earlier receipt remains unchanged.

At **19:11:59.495 UTC** the root normally closed the actual installed app and confirmed zero processes for that executable. At **19:12:24 UTC** a fresh packaged process launched from the exact installed EXE, with the same ASAR and own userData. All five stored jobs and all three final exported/completed/idle studies restored. The actual server model list was refreshed and a new Astra verification completed at **19:13:33 UTC**, text `Paper Factory connection works.` No research resume or scientific dispatch occurred. The app remains open and idle on Results. Physical monitor power state was not measured; Playwright renderer controls and Chromium captures used no OS screen framebuffer.

Final close/restart evidence is in the same Source12 proof directory: `final-normal-close.json` SHA256 `384a88a0429d1c22e94aab700e02d3de717c957b7f59256e15caca84c838f942`, `final-normal-restart-proof.json` `1693b39a8ab64a33d82330800e5b726ba084c5e995e38292e3fee41653a509af`, and `final-restart-runtime-meta.json` `39fcd4f50482c8f316e720cac29f6379d79204580efeb8fe39b2cc19f307e5b1`. Response/results ARIA and Chromium images are retained in `output/playwright/standalone-live-source12-23cb02e9-6db9-455a-af30-4396b0acebee/`. The Source12 app/SDK203/1skip and Electron4/20.2s checks remain current; unchanged Source11 Python794/7skip and all three runtime static comparisons remain applicable. Windows is unsigned and clean-VM validation is unperformed. Mac native execution/POSIX permissions/DMG/install/CI and DOCX page-layout visual checks remain unverified.

The independent live-WAL-aware SQLite read-only audit completed at **19:27:32.663325 UTC**. All17 fields and complete124/72/112 frozen files of the three valid studies exactly matched the root's pre-restart snapshots; all five jobs remained present. The old SemVer102 artifacts and original scientific hashes/execution count were retained. The old preview's current110 files passed full hashes, without claiming historical byte comparison where no baseline was supplied. Actual saved primary15/figure3, all913 ZIP members/907 inventory rows, current Markdown/TeX relative images and DOCX embedded images matched. Installed EXE/ASAR, the six configured bundled dist files and binding, runtime4463 and engine22 also matched. Actual writes/model/IPC/engine/UI calls were zero. The consolidated receipt is `.paper-factory/standalone-verification/final-restart-integrity-audit-b8af9974-a782-40af-93e0-2d2feaf1a4e0/final-readonly-integrity-summary.json`, SHA256 `6e32eb49c807e449c3521008cb5bca3894a3a0608690dd1f262885e30507720b`. Current delivery has no blocker; superseded archived manuscript image references are outside that delivery and remain untouched.
