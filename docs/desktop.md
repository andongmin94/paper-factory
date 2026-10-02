# Windows desktop development and distribution

The desktop application adapts `create-frontron` at commit
`3a7da2822721801db88ea059d204c8c6c622fab4`. The Electron main process owns a
private Python backend. React renders installed neobrutal-ui source components;
it does not receive backend session tokens, filesystem access or a shell API.

## Develop

Use Windows x64, Python 3.12, Node.js 24+ and npm on the **build machine**:

```powershell
.\scripts\setup_windows.ps1
npm.cmd ci --prefix desktop
npm.cmd run dev --prefix desktop
```

The existing `.venv` supplies the development backend. No server process needs
to be started separately. Development may override `PF_HOME` to use an isolated
test workspace. Packaged applications always use their own Electron user-data
directory, under `workspace/`; they do not reuse the source checkout's studies,
the current Codex desktop login or a global CLI profile.

## Build

```powershell
.\.venv\Scripts\python.exe scripts/bundle_desktop.py
npm.cmd run typecheck --prefix desktop
npm.cmd test --prefix desktop
npm.cmd run build --prefix desktop
& 'desktop/resources/runtime/python/python.exe' -B scripts/smoke_desktop_runtime.py
npm.cmd run package --prefix desktop
```

`desktop/output/` contains the Windows x64 installer and portable executable.
The installer build downloads electron-builder's Windows packaging tools. A
build has no publishing step and does not configure automatic updates or signing.
End users install/open the app and approve the official ChatGPT device login;
they do not install Python, Node, Git or Docker themselves.

The runtime builder copies the native Python standard library and executable,
then installs only locked application dependencies into a clean destination.
It copies backend source, a separate Node executable and its official license,
installs the fixed official Codex package, and downloads the official MinGit ZIP
with SHA-256 verification. It never copies a user's Python site-packages,
Codex home, `.env`, Git credentials or account cache. Every build requires the
checked-in `desktop/backend-requirements.txt`; the builder never resolves a new
dependency set or changes the lock. Runtime versions live in
`desktop/runtime-versions.json`. Electron and
React build dependency versions and transitive resolutions are in
`desktop/package.json` and `desktop/package-lock.json`.

`resources/runtime-manifest.json` records bundled versions and file hashes.
Runtime and upstream source licenses are retained with the application. Rebuild
the runtime after changing Python source or runtime pins, before packaging.
The app preserves the existing Windows AppContainer experiment isolation;
bundling Python into a single frozen executable would not supply the complete
runtime required by those workers.

## Connection and process ownership

The backend binds only `127.0.0.1` at a random available port. Every request,
including reads and artifact downloads, requires a fresh in-memory session
token. Electron validates IPC senders and allows only the research, account and
artifact operations exposed in the application. Renderer code has no Node
integration; context isolation and sandboxing remain enabled. Official device
login opens in the external browser. Documents are saved/opened through bounded
native dialogs, rather than arbitrary paths or remote URLs from the renderer.

First startup selects a logged-out state. Reopening the app restores local
records but does not automatically resume research or spend model calls.
Connecting and connection verification are explicit actions. Verification
consumes one subscription model call. No separate registration, member schema,
account email collection or central application backend exists.

Logout calls the official CLI only inside the selected profile and the current
pending app-owned private profile. Older inactive profile directories remain
unselected; this does not purge every historical cached account.
It confirms local logout before reporting completion and persists a logged-out
marker so another application/global login cannot be selected accidentally.
Research must finish or be stopped before login, account switching or logout.
Logout leaves papers and research records intact. The app waits for owned
research and authentication workers before exiting; if cleanup cannot be
confirmed, it remains open and explains why closing could not complete.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_desktop.py tests/test_web_connection.py tests/test_autonomous_connection.py tests/test_autonomous_provider.py
npm.cmd run typecheck --prefix desktop
npm.cmd test --prefix desktop
npm.cmd run lint --prefix desktop
```

These checks use synthetic accounts/providers. They do not log out an actual
account, approve device authentication or start paid research. Inspect a packaged
app with a fresh data directory as well: dependency checks must pass with no
system Python/Node/Git on PATH. A release still needs signing and a clean-machine
installation check before it can be described as production-tested.
