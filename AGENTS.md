# Paper Factory development

Paper Factory is a native Rust + GPUI manuscript desktop app. Think Tank is a separate research skill; GPUI Design is a separate UI foundation.

## Current state

Only the repository baseline exists. There is no runnable app, Cargo project, implemented agent integration, or validated UI yet. Keep README.md accurate as working capabilities are added.

## Implementation

- Use Rust, GPUI, and andongmin94/gpui-design. Do not introduce Electron, a webview, or an Overleaf fork.
- Inspect the current GPUI Design API and dependency pins before adding Cargo dependencies. Do not copy a guessed version or assume Textarea is a complete LaTeX editor.
- Start with a native app that opens, edits, and saves a local .tex file end to end. Add compilation and PDF preview on that working baseline.
- Reuse established dependencies where they reduce complexity. Keep editing, compilation, PDF display, and agent integration concerns separate without speculative frameworks.
- Keep Think Tank and GPUI Design independently maintained; do not duplicate either repository here.
- Verify official agent interfaces and authentication terms before implementing Claude Code or Codex integration. Do not collect subscription OAuth credentials or silently substitute paid API calls.
- Never overwrite unsaved manuscript edits with agent output. Keep private research files and credentials out of this source repository.

## Scope and verification

- Implement the smallest complete change for the current requirement or observed failure. Remove obsolete paths instead of adding compatibility layers, migrations, or fallbacks.
- Use existing verification tools. Run checks matched to the change; repeat a passing check only after a relevant change, new failure, concrete unresolved concern, or mandatory requirement.
- Do not repeatedly rebuild or retest the whole system during intermediate edits. Integrate checks on the completed change set.
- Use Git and a short current-state section in README.md. Do not accumulate duplicate snapshots or historical status documents.
- Report source changes, checks actually run, and unverified behavior separately. Do not label scaffolding as an implemented product.
