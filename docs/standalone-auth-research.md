# Standalone ChatGPT authentication research

Inspected on 2026-10-05 using official OpenAI documentation before repository source. This document records implementation inputs. It does not establish successful login, account entitlement, or inference in Paper Factory.

## Official integration contract

The local open-source flow dynamically registers Paper Factory during browser authorization. It requires no API key or client secret. Each installation keeps one stable host ID; each account/workspace registration keeps its own issued client ID. Login validates the returned identity before making the new connection active. The initial `dynamic_agent_client` value must never be saved as the issued registration. [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)

The official example places authentication, storage, and model calls in Electron main and exposes credential-free state through a preload bridge. The user approves ChatGPT plan use separately from identity. Eligible Plus/Pro accounts can use the local open-source route, subject to their account/workspace policy and allowance. A connected badge does not prove successful inference. [OpenAI cookbook](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)

Model discovery uses the active account's OAuth access token with `GET https://api.openai.com/v1/models`, keeps visible entries in server order, displays `display_name`, and submits `slug`. Requests use `POST https://api.openai.com/v1/responses` with `store:false` and `stream:true`. Only `response.completed` establishes completion; partial output, interrupted streams, `response.failed`, and `response.incomplete` remain failures. [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)

Send the context required for each HTTP request as an input array, using user, assistant, or developer messages and optional instructions. Omit HTTP `previous_response_id`. Unsupported request fields include background, conversation, max_output_tokens, max_tool_calls, metadata, moderation, multi_agent, prompt, prompt_cache_retention, safety_identifier, temperature, top_logprobs, top_p, truncation, and user. Hosted image generation, file search, Code Interpreter, native computer use, hosted MCP/connectors, and tool_search are unavailable on this route. [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

The app retains distinct profile registrations even when their email labels match. Selecting an account cancels requests associated with the previous account. Logout stops requests, attempts refresh-token revocation, removes selected tokens locally, and retains its registration for later sign-in. Failed remote revocation must be disclosed. Refresh rotation must be serialized and durably saved. [Accounts and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)

Access expiry is supplied by the token response; the reference currently documents one-hour access tokens and rotating 30-day refresh tokens. Use response expiry and the SDK refresh policy rather than implementing a second refresh scheduler. [Token reference](https://developers.openai.com/siwc/token-sharing-open-source/token-reference)

## Pinned SDK and packaging

The cookbook links the official [Sign in with ChatGPT DevKit](https://github.com/openai/sign-in-with-chatgpt-devkit). The inspected commit is `f723814abdccec135b519c451fb6e1992ee5e933`. Its `@siwc/local` package is a private local workspace at version 0.1.0. The public npm registry returned HTTP 404 for `@siwc/local` during this inspection.

Paper Factory initially vendored `packages/local/src` and `packages/local/test` unchanged in `desktop/vendor/siwc-local`, with source/test SHA256 values matching the pinned upstream files and only package/build metadata adapted. On 2026-10-05 it added the narrow SSE deadline change and three local regression tests documented below; the current `src/responses.ts` is therefore not byte-identical to upstream. Runtime dependencies are `jose` and `proper-lockfile`; the latter's TypeScript declarations are supplied by `@types/proper-lockfile`. The root app builds this workspace before compiling its Electron main process. It must not run the complete DevKit's macOS-native Paste Perfect build.

The upstream code has the Sign-in with ChatGPT DevKit Noncommercial License v1.0. Its grant is limited to noncommercial purposes, and independent software does not acquire that license merely by calling the SDK. Paper Factory preserves the complete license, third-party notices, and upstream dependency inventory. These notices must accompany compiled SDK redistribution. This upstream inventory includes the original examples and is not a complete inventory of the Paper Factory installer. [Pinned license](https://github.com/openai/sign-in-with-chatgpt-devkit/blob/f723814abdccec135b519c451fb6e1992ee5e933/LICENSE)

## Main-process API

The pinned exports are `createChatGPT`, `ChatGPTError`, `CHATGPT_USAGE_URL`, and public credential-free session/profile/model types. The runtime uses this configuration:

```ts
createChatGPT({
  appName: 'Paper Factory',
  appId: 'paper-factory',
  redirectPort: 0,
  storageDir: join(app.getPath('userData'), 'chatgpt'),
  credentialEncryption,
  sendHostId: true,
  openBrowser: url => shell.openExternal(url),
});
```

`redirectPort:0` selects an available IPv4 loopback port. The SDK checks callback host/path/state, uses PKCE and nonce, discovers OAuth endpoints, and verifies ID-token issuer, signature, audience, and subject. The issued client ID is saved before code exchange, allowing a later attempt to reuse a registration when exchange fails. [Pinned OAuth implementation](https://github.com/openai/sign-in-with-chatgpt-devkit/blob/f723814abdccec135b519c451fb6e1992ee5e933/packages/local/src/oauth.ts)

| Method | Pinned signature and behavior |
| --- | --- |
| `signIn` | `{signal?,newProfile?,profileId?,label?,reconsent?}` → safe session. `newProfile:true` adds a registration; `profileId` reconnects one. |
| `cancelSignIn` | Cancels pending authorization and closes its callback listener. |
| `getSession` | Restores safe state; it does not establish model usage. |
| `listProfiles` | Returns distinct IDs, stable labels, safe identity, status, and permission flags. |
| `selectProfile(id)` | Cancels active account requests, persists the selected profile, returns safe session. |
| `listModels({signal?})` | Discovers active-account models after any required refresh. |
| `subscribe(listener)` | Immediately emits safe state and returns an unsubscribe function. |
| `disconnect` | Attempts revocation, removes selected tokens locally, retains registration/identity. |
| `streamResponse` | `{model,input,instructions?,signal?,onDelta?}` → `{text}` only after completed inference. |

`input` accepts a string or an array of `{role:'user'|'assistant'|'developer',content:string}`. The SDK converts a string into the required array before transmission. Its exposed response options cannot add unsupported request fields. The returned session status is `disconnected`, `connecting`, `connected`, or `reauth_required`; `sharing` additionally requires usable credentials and the actual granted `chatgpt.tokens.use.direct` scope. [Pinned types](https://github.com/openai/sign-in-with-chatgpt-devkit/blob/f723814abdccec135b519c451fb6e1992ee5e933/packages/local/src/types.ts)

## Protected storage and cancellation

`CredentialEncryption` requires a stable provider ID, availability check, and encrypt/decrypt functions. Create the adapter after Electron readiness, with `electron-safe-storage-v1`, `safeStorage.isEncryptionAvailable()`, `safeStorage.encryptString()`, and `safeStorage.decryptString(Buffer.from(ciphertext))`. Windows uses Electron's OS-backed protected storage; macOS uses its Keychain-backed provider. There is no app plaintext fallback. The upstream adapter additionally refuses Linux's hardcoded-key basic_text backend. [Pinned Electron adapter](https://github.com/openai/sign-in-with-chatgpt-devkit/blob/f723814abdccec135b519c451fb6e1992ee5e933/examples/paste-perfect/electron/credential-encryption.ts)

All registration data, labels, access/refresh/ID tokens, and pending token rotation are encrypted in `chatgpt-auth.json`. `chatgpt-host.json` contains the non-secret installation identifier. The store uses interprocess locking and atomic replacement, with Unix owner-only permissions. Decryption/provider failures preserve the file and surface an error. Refresh rotation is durably checkpointed before identity verification, so a signing-key outage does not discard the sole replacement refresh token. [Pinned storage](https://github.com/openai/sign-in-with-chatgpt-devkit/blob/f723814abdccec135b519c451fb6e1992ee5e933/packages/local/src/storage.ts)

The SDK includes a ten-minute sign-in deadline, but maps both timeout and explicit abort to `cancelled`. The app must distinguish its own explicit cancellation from elapsed authorization timeout to meet the UI requirement. Use a tracked main-process deadline without rewriting OAuth. Logout attempts revocation twice, allowing ten seconds per request with 300 ms backoff for network/5xx failures. A `revocation_failed` exception can accompany the correctly restored local disconnected state. [Pinned runtime](https://github.com/openai/sign-in-with-chatgpt-devkit/blob/f723814abdccec135b519c451fb6e1992ee5e933/packages/local/src/index.ts)

## Error and verification requirements

Preserve safe HTTP status, machine code, request ID, and response-shape diagnostics. A permission-less identity connection cannot start inference. Usage limits pause new plan calls and offer Manage usage, without inferring the reset time. Temporary network/service failures preserve credentials. HTTP 401 alone does not establish revocation. Terminal refresh errors require reauthorization with the saved registration. Reconsent is an explicit user action, not ordinary startup behavior. The user explicitly excludes API-key fallback. [Errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)

| SDK code or state | App action |
| --- | --- |
| `cancelled` | Report cancellation; distinguish app deadline as login expiry. |
| `access_denied` | Report that browser consent was not completed. |
| `sharing_not_enabled` / connected with `sharing:false` | Keep account identity; offer explicit plan-permission reconnection. |
| `subscription_sharing_user_not_eligible` | Explain unavailable account/workspace access; do not loop OAuth. |
| `subscription_sharing_usage_limit_exceeded` | Stop new requests and open ChatGPT usage management. |
| `subscription_sharing_usage_unavailable`, `network_error` | Preserve connection and allow later retry. |
| `subscription_sharing_unsupported_capability`, `invalid_request` | Fix the request; do not repeat it unchanged. |
| `invalid_refresh_token`, `refresh_token_expired`, related terminal refresh failures | SDK clears unusable tokens and marks reauthentication required. |
| `storage_encryption_unavailable`, `storage_decryption_failed` | Preserve original file; display protected-storage failure. |
| `response_incomplete`, `stream_interrupted` | Preserve partial display as failure; never record success. |
| `revocation_failed` | Show local sign-out with remote revocation unconfirmed. |

The app's stage-one receipt should record app version, selected model, start/completion time, completion success, and output SHA256. SDK `{text}` does not expose the server response ID. Do not modify the SDK merely to fabricate an ID; a separately described request receipt is sufficient for this gate.

Required stage-one checks remain distinct: synthetic regression tests; actual OS encrypted-storage persistence across a restart; actual Paper Factory browser authorization; active-account model discovery; nonempty completed subscription response; and app restart restoring that same safe connection. Only the actual login and inference checks unlock the user-requested research implementation gate. No other application's credential file is inspected or imported.

## SDK verification performed

At the initial Windows checkpoint, `npm run build --workspace @siwc/local` completed successfully. `npm run test --workspace @siwc/local` ran 46 upstream tests: 45 passed, zero failed, and one Unix owner-only/symlink-enforcement case was skipped on Windows. The suite uses synthetic credentials, local loopback callbacks, mock network responses, and an in-memory test encryption provider. It confirms regression behavior, not actual ChatGPT authorization or the OS safeStorage provider. Actual app authorization, model discovery, completed subscription inference and restart restoration subsequently passed the separate gate recorded in `standalone-verification.md`; these initial mock tests remain historical evidence.

The initial additional `desktop/tests/responses.test.mjs` ran against the then-unchanged compiled SDK's actual model discovery and SSE parser: 11 tests passed. It checks the public endpoint, synthetic OAuth bearer, exact supported body fields, array history, rejected system messages, catalog visibility/order, split CRLF events, required completion, usage failure after deltas, incomplete/interrupted streams, reader errors, and cancellation. Global fetch is mocked, so these checks make no network request and read no account credentials. Actual GUI/auth is not established by these tests.

An isolated source copy with fresh `node_modules` under `.paper-factory/standalone-clean-install-7ec372c98e574b0e9e3be0869bfbccbd` passed `npm ci --no-audit --no-fund` (exit 0, 611 packages) using Node v24.21.0/npm 12.2.0 without an `allow-remote` override. `npm run build` then passed SDK compilation, app type checking, main bundling, and Vite rendering (exit 0, 1981 modules). The first desktop-only fixture omitted the repository LICENSE required by the build; that initial failure and the successful run after copying the unchanged repository license are both retained. Logs, exit codes, source hashes, and a verification receipt remain in that ignored evidence directory. No Electron executable or UI was launched by these checks. This verifies a fresh dependency tree on the current Windows development host, not an installation on a machine without development tools or actual authentication.

## SSE deadline and authoring safeguards — 2026-10-05 12:45 UTC

The actual Frontron manuscript-review request `30607f66…`, started at 12:22:15 UTC, failed at 12:25:15.746 UTC with `stream_interrupted` when the former 180-second SDK fetch deadline ended the streamed body. Its retained 4,091-character partial response is failed evidence, not an accepted review or a completed inference. This client deadline is separate from account usage limits and OAuth token expiry.

`src/responses.ts` now passes `10 * 60_000` to `fetchRemote`, matching the app's bounded ten-minute authoring budget. Explicit caller cancellation remains `cancelled`; an unfinished stream at the SDK deadline remains a failure, and success still requires the actual `response.completed` event. The request continues to use the public OAuth route, supported message array and `store:false`/`stream:true`; the deadline change adds no request field or credential fallback. Current source SHA256: `16cfdeb15dc1ae2a7209c4b383c9f8e9a52ffe0fc275a410c7ed0cdcd297a5ea`.

The added `test/response-deadline.test.mjs` uses mocked fetch and timers to verify completion after the former cutoff, caller abort after SSE headers, and rejection of unfinished partial output after ten minutes. Its SHA256 is `4e833e9ef6705b50d131a8da22c15f0aa01fdddde08bd3803917e23f56f188562`. The combined app/SDK run passed **101 tests**: 53 desktop and 48 SDK, with one Windows skip and zero failures. Proof: `.paper-factory/standalone-verification/stream-deadline-20261005-487dcc5597df4b3d9e1725d97cfbe132/npm-test.txt`, SHA256 `ead3b8e9765771da664153e3cc715afcb0804de6ae947aee136e45f4e24a2350`. These are synthetic transport/controller tests, not another live model response.

Explicit research resume now starts/checks the runtime and obtains retained workflow status before model validation. Engine transport failures invalidate cached readiness. A live controller task or startup lease rejects a simultaneous resume; durable started/completed/failed/interrupted model receipts are reconciled before subsequent work. This does not convert an unresolved started receipt or partial response into completed review evidence and does not authorize another scientific dispatch.

The authoring prompt requires disclosure of every frozen resource bound and actual sampling/call count. It excludes mutable drafting-interface and review-status commentary from the scientific manuscript; the fresh reviewer checks those claims against retained evidence. A model draft assessment remains distinct from journal peer review and scientific validity. The previous protocol-invalid preview report contributes zero successful papers; the goal remains **0/3** at this checkpoint.

The separate plotting startup fix, Windows runtime `303c08c185c3f5054609c96d116bb71e28696937cc0e2c63c93b167a5d81b4ea`, and latest Mac static profiles are recorded with source/receipt hashes in `standalone-verification.md`. At 12:45 UTC the correct full Python rerun, final NSIS verification and sixth installed-app check are pending. Earlier actual connection success does not establish those newer installation checks, and no native Mac execution, login, DMG installation or CI result is claimed.

## Research suitability and manuscript review — 2026-10-06

Three actual 0.13.1 runs produced retained function experiments and manuscripts, but their contribution, comparator choice, and related literature were insufficient for useful research papers. Successful inference, reproducible measurements, and a readable PDF establish separate technical facts; none establishes scholarly quality. Those original runs and reviews remain unchanged and are not retrospectively approved under the new criteria.

The revised source flow is `created → proposed → planned → code_ready → analyzed → manuscript → exported`. A proposal is not a frozen protocol. After collecting literature, a fresh reviewer-model request evaluates the research question, contribution, literature relevance, comparison, sampling, and feasibility. Its `StudyReview` records a passed flag and reason for every criterion, issues, and selected source/excerpt IDs with relevance explanations. Only an accepted assessment allows the engine to freeze the protocol as `planned` and request experiment code. Selected source IDs must refer to retained literature; model-selected references do not establish facts absent from the retained excerpts.

The controller makes at most three proposal/review attempts, including the initial proposal. It retains rejected proposals, assessment artifacts, and model request receipts. If no proposal passes, it leaves the workflow at `proposed`, marks it blocked with `STUDY_REJECTED`, and makes no scientific dispatch or paper export. Ordinary preparation resume is not allowed for that final rejection. A new research request can use a revised goal and comparison method; it does not replace the rejected evidence. Interrupted, otherwise resumable `proposed` work remains part of preparation.

The manuscript assessment now also records contribution, literature use, interpretation, and presentation as separate passed/reason judgments alongside accepted/issues/checks. It must distinguish independent sampling units from metric rows and repeated function calls, keep claims within the actual experiment's scope, and avoid treating trivial controls as evidence of a new contribution. A final manuscript rejection is `MANUSCRIPT_REJECTED`; raw observations and reviewer evidence remain retained, and rejected writing is not exported as a completed paper. Experiment-code reviews retain their existing distinct `REVIEW_REJECTED` failure.

The renderer displays `연구 적합성 검토`, `연구 보류`, and `원고 보류` with criterion reasons and issues. An export is labelled `원고 생성 완료`. These are model judgments, not journal peer review, acceptance, a numerical quality score, or a guarantee of originality. The available experiment runtime remains bounded QuickJS for supported JS/TS functions. When that runtime cannot answer the research question, the feasibility assessment must fail rather than convert an isolated helper test into an application-level claim.

Completed exports from the earlier flow remain available for opening and saving. Without the current study and manuscript assessments, they do not offer the writing-revision action. Revising such a paper cannot manufacture a missing pre-execution design approval. For new completed studies, revision uses retained measurements and fresh writing/review requests; it does not repeat the experiment.

This section originally described the source change before packaging. The verified 0.14.0 installer now includes this flow; the historical 0.13.1 installer does not. Synthetic regression checks remain distinct from a new authenticated installed-app run, a successful scholarly study, or an externally reviewed publication.

## Quality verification and native documents — 2026-10-07

The 0.14.0 source treats both `STUDY_REJECTED` and `STUDY_INFEASIBLE` as a research hold. If the available runtime and retained evidence cannot support a suitable design, the controller stops without forcing three attempts, dispatching an experiment, or generating a manuscript. Neither terminal hold offers ordinary resume. The user can start a new study with a revised question and comparison method. Writing revision requires accepted current study and manuscript reviews together; retained earlier exports disclose missing review records and remain available for opening and saving.

Literature collection attempts every proposed query before allocating candidates across queries. An explicit DOI uses an exact Crossref lookup. Metadata records remain distinct from inspected abstracts or allowed full-text excerpts. If a later collection obtains readable content for a previously retained DOI, the engine records the richer source and excerpt evidence instead of silently retaining metadata alone. Approval requires complete retrieval attempts and binds selected source/excerpt IDs to the retained reading scope; relevance remains a separate reviewer judgment.

Native PDF tables use five compact columns with a count column wide enough for the supported maximum of 10,000 observations. Trusted Typst presentation rules wrap long ASCII identifiers in 9pt table cells without truncating labels, changing scientific values, or shrinking body text. Source Markdown, full-precision analysis JSON/CSV and DOCX cell values retain their original contents. Pretendard regular and bold fonts are supplied directly by the engine. The unused plotting dependency chain and startup warmup were removed; development installation now uses `.[dev,pdf]`.

The actual model evaluation re-reviewed the first study proposal from each of the retained ARTEX, Premiere and Frontron protocols. All three were rejected. The negative harness intentionally stopped after the native engine durably recorded that first assessment; it made no planning, code-generation, scientific execution or manuscript request. It does not establish the controller's complete retry behavior or general classifier accuracy. A separate Premiere algorithm candidate stopped with `STUDY_INFEASIBLE`: a bounded function experiment was technically possible, but the retained literature did not justify an additional research contribution. Its execution attempt count remained zero and no new manuscript was generated.

Final Python regression checks passed 967 tests with seven skips: five Windows symlink-permission cases and two macOS-native guardian/EOF cases. Desktop checks passed 223 tests, the SDK passed 48 with one Windows skip, and all 11 background Electron cases passed without retries against the final production build and trimmed runtime. Fresh owned app-data directories and hidden offscreen windows kept these fixtures separate from user credentials and normal desktop work. The PDF conversion/layout subset passed 26 tests, including 2/8-condition tables with both 36 and 10,000 observations, complete long metric/unit/condition labels, native text positions and unchanged DOCX values. Visual QA inspected eight synthetic PDFs across nine pages: six result-table variants, a mixed Korean/English regular/bold font fixture, and a two-page concise native manuscript. These fixtures verify readable conversion and content preservation, not research contribution or a live-model manuscript approval.

The final Windows 0.14.0 NSIS installer passed static package verification at `2026-10-07T00:36:18.981Z`. App/SDK imports, renderer assets, local Pretendard, engine source and all 2,218 runtime file hashes matched. A separate fresh bundled-runtime smoke confirmed QuickJS readiness and cleanup, an empty initial workflow list, clean shutdown/exit zero, and valid Korean PDF/DOCX/TeX outputs with embedded Pretendard regular/bold. It used zero model calls and zero scientific dispatches. Static package verification and native-runtime smoke do not establish freshly installed distribution GUI behavior, new OAuth authorization, restart authentication or an approved live-model paper. Installer and verification hashes are recorded in the [dated 0.14.0 verification section](standalone-verification.md#0140-연구-품질-설계와-최종-검증-2026-10-07).
