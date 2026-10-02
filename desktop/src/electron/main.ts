import { existsSync, promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  protocol,
  session,
  shell,
  type IpcMainInvokeEvent,
} from "electron";
import { Backend, boundedBytes } from "./backend.js";
import {
  artifactName,
  isTrustedFrame,
  MAX_ARTIFACT,
  validateApiRequest,
  validateArtifactPath,
  validateDeviceUrl,
} from "./security.js";

const runtimeDirectory = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(runtimeDirectory, "../..");
const scheme = "paperfactory";
const productionUrl = `${scheme}://app/`;
const isDev = !app.isPackaged;
let window: BrowserWindow | null = null;
let backend: Backend | undefined;
let rendererUrl = productionUrl;
let shutdownComplete = false;
let shutdownPending = false;
let artifactDirectory: string | undefined;

protocol.registerSchemesAsPrivileged([
  {
    scheme,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

function backendEnvironment(): { executable: string; cwd: string; env: NodeJS.ProcessEnv } {
  const repositoryRoot = path.dirname(desktopRoot);
  const resourceRoot = process.resourcesPath;
  const workspace =
    isDev && process.env.PF_HOME
      ? path.resolve(process.env.PF_HOME)
      : path.join(app.getPath("userData"), "workspace");
  const executable = isDev
    ? path.join(repositoryRoot, ".venv", "Scripts", "python.exe")
    : path.join(resourceRoot, "runtime", "python", "python.exe");
  if (!existsSync(executable))
    throw new Error("Python 실행환경이 없습니다. 개발 환경 또는 설치 패키지를 확인해 주세요.");
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (
      [
        "CODEX_HOME",
        "OPENAI_API_KEY",
        "OPENAI_ADMIN_KEY",
        "OPENAI_ORG_ID",
        "OPENAI_PROJECT_ID",
        "PYTHONHOME",
        "PYTHONPATH",
        "ELECTRON_RUN_AS_NODE",
      ].includes(key.toUpperCase())
    )
      delete env[key];
  }
  env.PF_HOME = workspace;
  env.PF_CODEX_AUTH_HOME = path.join(workspace, "codex-auth");
  env.PYTHONUNBUFFERED = "1";
  env.PYTHONDONTWRITEBYTECODE = "1";
  env.PYTHONUTF8 = "1";
  env.PYTHONPATH = isDev ? path.join(repositoryRoot, "src") : path.join(resourceRoot, "backend");
  if (isDev) {
    env.PF_CODEX_BIN = path.join(
      repositoryRoot,
      ".venv",
      "codex",
      "node_modules",
      ".bin",
      "codex.cmd",
    );
  } else {
    delete env.PYPANDOC_PANDOC;
    env.PF_NODE_BIN = path.join(resourceRoot, "runtime", "node", "node.exe");
    env.PF_CODEX_BIN = path.join(
      resourceRoot,
      "runtime",
      "codex",
      "node_modules",
      ".bin",
      "codex.cmd",
    );
    const inheritedPath =
      Object.entries(env).find(([key]) => key.toUpperCase() === "PATH")?.[1] ?? "";
    for (const key of Object.keys(env)) if (key.toUpperCase() === "PATH") delete env[key];
    env.PATH = [
      path.join(resourceRoot, "runtime", "git", "cmd"),
      path.join(resourceRoot, "runtime", "git", "ucrt64", "bin"),
      path.dirname(env.PF_NODE_BIN),
      inheritedPath,
    ].join(path.delimiter);
  }
  return { executable, cwd: isDev ? repositoryRoot : resourceRoot, env };
}

function requireSender(event: IpcMainInvokeEvent): void {
  if (
    !window ||
    !event.senderFrame ||
    !isTrustedFrame(
      event.sender.id,
      window.webContents.id,
      event.senderFrame === window.webContents.mainFrame,
      event.senderFrame.url,
      rendererUrl,
    )
  )
    throw new Error("허용되지 않은 화면 요청입니다.");
}

function installHandlers(): void {
  const handle = (channel: string, callback: (...args: unknown[]) => unknown) =>
    ipcMain.handle(channel, (event, ...args) => {
      requireSender(event);
      return callback(...args);
    });
  handle("paperfactory:runtime", () => {
    if (!backend?.ready) throw new Error("백엔드가 연결되어 있지 않습니다.");
    return { version: app.getVersion(), platform: process.platform, backend: "ready" };
  });
  handle("paperfactory:request", (method, route, body) => {
    const request = validateApiRequest(method, route, body);
    return backend!.json(request.path, { method: request.method, body: request.body });
  });
  handle("paperfactory:external", (url) => shell.openExternal(validateDeviceUrl(url)));
  handle("paperfactory:artifact-save", async (route) => {
    const safeRoute = validateArtifactPath(route);
    const selection = await dialog.showSaveDialog(window!, {
      title: "결과 파일 저장",
      defaultPath: artifactName(safeRoute),
    });
    if (selection.canceled || !selection.filePath) return { canceled: true };
    const response = await artifactResponse(safeRoute);
    await fs.writeFile(selection.filePath, await boundedBytes(response, MAX_ARTIFACT));
    return { canceled: false, path: selection.filePath };
  });
  handle("paperfactory:artifact-open", async (route) => {
    const safeRoute = validateArtifactPath(route);
    const response = await artifactResponse(safeRoute);
    artifactDirectory ??= await fs.mkdtemp(path.join(os.tmpdir(), "paperfactory-view-"));
    const entryDirectory = await fs.mkdtemp(path.join(artifactDirectory, "artifact-"));
    const filename = path.join(entryDirectory, artifactName(safeRoute));
    await fs.writeFile(filename, await boundedBytes(response, MAX_ARTIFACT), { flag: "wx" });
    const error = await shell.openPath(filename);
    if (error)
      throw new Error("이 파일을 열 기본 프로그램을 찾지 못했습니다. 파일을 저장해서 열어 주세요.");
  });
}

async function artifactResponse(route: unknown): Promise<Response> {
  const response = await backend!.fetch(validateArtifactPath(route));
  if (!response.ok) {
    await response.body?.cancel();
    throw new Error("결과 파일을 읽을 수 없습니다.");
  }
  return response;
}

async function installRendererProtocol(): Promise<void> {
  const rendererRoot = path.join(desktopRoot, "dist", "renderer");
  const mime: Record<string, string> = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".json": "application/json",
  };
  await protocol.handle(scheme, async (request) => {
    try {
      const url = new URL(request.url);
      if (url.host !== "app" || request.method !== "GET")
        return new Response("Not found", { status: 404 });
      const relative = decodeURIComponent(url.pathname).replace(/^\/+/, "") || "index.html";
      if (relative.includes("\\") || relative.includes("\0"))
        return new Response("Not found", { status: 404 });
      const filename = path.resolve(rendererRoot, relative);
      const resolvedRelative = path.relative(rendererRoot, filename);
      if (
        resolvedRelative.startsWith("..") ||
        path.isAbsolute(resolvedRelative) ||
        !mime[path.extname(filename)]
      )
        return new Response("Not found", { status: 404 });
      return new Response(await fs.readFile(filename), {
        headers: {
          "Content-Type": mime[path.extname(filename)],
          "Content-Security-Policy":
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'none'; frame-src blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
          "X-Content-Type-Options": "nosniff",
        },
      });
    } catch {
      return new Response("Not found", { status: 404 });
    }
  });
}

function createWindow(): void {
  window = new BrowserWindow({
    title: "Paper Factory",
    show: false,
    width: 1440,
    height: 960,
    minWidth: 980,
    minHeight: 680,
    icon: path.join(desktopRoot, "public", "icon.png"),
    webPreferences: {
      preload: path.join(runtimeDirectory, "preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      webviewTag: false,
    },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event) => event.preventDefault());
  window.webContents.on("will-redirect", (event) => event.preventDefault());
  window.webContents.on("will-frame-navigate", (details) => {
    if (details.isMainFrame || !details.url.startsWith("blob:")) details.preventDefault();
  });
  window.on("close", (event) => {
    if (!shutdownComplete) {
      event.preventDefault();
      app.quit();
    }
  });
  window.on("closed", () => {
    window = null;
  });
  window.once("ready-to-show", () => window?.show());
  void window.loadURL(rendererUrl).catch(() => {
    dialog.showErrorBox("Paper Factory", "화면을 불러오지 못했습니다.");
    app.quit();
  });
}

async function initialize(): Promise<void> {
  await app.whenReady();
  session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) =>
    callback(false),
  );
  session.defaultSession.setPermissionCheckHandler(() => false);
  if (isDev) {
    const candidate = new URL(process.env.ELECTRON_RENDERER_URL ?? "http://127.0.0.1:5173/");
    if (
      candidate.protocol !== "http:" ||
      candidate.hostname !== "127.0.0.1" ||
      candidate.port !== "5173" ||
      candidate.pathname !== "/" ||
      candidate.username ||
      candidate.password ||
      candidate.search ||
      candidate.hash
    )
      throw new Error("개발 화면은 전용 로컬 Vite 주소에서 실행해야 합니다.");
    rendererUrl = candidate.href;
  } else await installRendererProtocol();
  const rendererOrigin = new URL(rendererUrl).origin;
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    let allowed =
      details.url.startsWith(`${scheme}://app/`) ||
      details.url.startsWith("blob:") ||
      details.url.startsWith("data:");
    if (isDev) {
      try {
        const url = new URL(details.url);
        allowed ||=
          url.origin === rendererOrigin ||
          (url.protocol === "ws:" && url.hostname === "127.0.0.1" && url.port === "5173");
      } catch {
        /* deny malformed URLs */
      }
    }
    callback({ cancel: !allowed });
  });
  if (isDev)
    session.defaultSession.webRequest.onHeadersReceived((details, callback) =>
      callback({
        responseHeaders: {
          ...details.responseHeaders,
          "Content-Security-Policy": [
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src http://127.0.0.1:5173 ws://127.0.0.1:5173; frame-src blob:; object-src 'none'; base-uri 'self'",
          ],
        },
      }),
    );
  backend = new Backend({
    ...backendEnvironment(),
    args: ["-m", "paper_factory.desktop", "--port", "0"],
  });
  await backend.start();
  installHandlers();
  Menu.setApplicationMenu(null);
  createWindow();
}

async function shutdown(): Promise<void> {
  if (shutdownPending) return;
  shutdownPending = true;
  let retry = false;
  try {
    await backend?.stop();
    // Remove only this process's randomly created viewer cache.
    if (
      artifactDirectory &&
      path.dirname(artifactDirectory) === path.resolve(os.tmpdir()) &&
      path.basename(artifactDirectory).startsWith("paperfactory-view-")
    )
      await fs.rm(artifactDirectory, { recursive: true, force: true }).catch(() => {});
    shutdownComplete = true;
    app.quit();
  } catch {
    const result = await dialog.showMessageBox({
      type: "warning",
      title: "Paper Factory",
      message: "작업의 안전한 종료를 확인하지 못했습니다.",
      detail: "앱을 유지하고 진행 중인 작업을 확인하거나 종료를 다시 시도해 주세요.",
      buttons: ["앱 유지", "종료 다시 시도"],
      defaultId: 0,
      cancelId: 0,
    });
    retry = result.response === 1;
  } finally {
    shutdownPending = false;
  }
  if (retry) void shutdown();
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => {
    if (window?.isMinimized()) window.restore();
    window?.show();
    window?.focus();
  });
  app.on("before-quit", (event) => {
    if (!shutdownComplete) {
      event.preventDefault();
      void shutdown();
    }
  });
  app.on("window-all-closed", () => app.quit());
  process.on("SIGINT", () => app.quit());
  process.on("SIGTERM", () => app.quit());
  if (isDev) {
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (data) => {
      if (String(data).trim() === "paperfactory:quit") app.quit();
    });
  }
  initialize().catch(async (error: unknown) => {
    dialog.showErrorBox(
      "Paper Factory 시작 실패",
      error instanceof Error ? error.message : "앱을 시작할 수 없습니다.",
    );
    if (!backend?.ready) {
      shutdownComplete = true;
      app.quit();
    } else await shutdown();
  });
}
