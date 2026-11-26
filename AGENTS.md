# Paper Factory development

Paper Factory is a native Rust + GPUI manuscript desktop app. Think Tank is a separate research skill; GPUI Deck is a separate headless UI foundation.

## Current state

A single-file `.tex` editor with highlighting, an outline, Tectonic compilation, and a hayro PDF preview runs on Windows. There is no multi-file project support or agent integration yet. README.md lists what has and has not been verified; keep it accurate as capabilities are added.

## Implementation

- Use Rust, GPUI, and andongmin94/gpui-deck. Do not introduce Electron, a webview, or an Overleaf fork.
- Inspect the current GPUI Deck API and dependency pins before adding Cargo dependencies. Pin the gpui-pre crate family and Rust toolchain to the versions GPUI Deck uses, together; do not copy a guessed version.
- Build the manuscript editor on GPUI Deck's `EditorState`, not `Textarea`, which has no line numbers, folding, highlighting, or LSP hooks. GPUI Deck ships no parser or PDF display: implement LaTeX highlighting through its `InputHighlighter`/`LanguageProvider` seams and PDF preview in this app.
- Korean IME composition in the editor is not validated upstream; check it on a real desktop and report it separately from headless tests.
- Start with a native app that opens, edits, and saves a local .tex file end to end. Add compilation and PDF preview on that working baseline.
- Reuse established dependencies where they reduce complexity. Keep editing, compilation, PDF display, and agent integration concerns separate without speculative frameworks.
- Keep Think Tank and GPUI Deck independently maintained; do not duplicate either repository here.
- Verify official agent interfaces and authentication terms before implementing Claude Code or Codex integration. Do not collect subscription OAuth credentials or silently substitute paid API calls.
- Never overwrite unsaved manuscript edits with agent output. Keep private research files and credentials out of this source repository.

## Scope and verification

- Implement the smallest complete change for the current requirement or observed failure. Remove obsolete paths instead of adding compatibility layers, migrations, or fallbacks.
- Use existing verification tools. Run checks matched to the change; repeat a passing check only after a relevant change, new failure, concrete unresolved concern, or mandatory requirement.
- Do not repeatedly rebuild or retest the whole system during intermediate edits. Integrate checks on the completed change set.
- Use Git and a short current-state section in README.md. Do not accumulate duplicate snapshots or historical status documents.
- Report source changes, checks actually run, and unverified behavior separately. Do not label scaffolding as an implemented product.
