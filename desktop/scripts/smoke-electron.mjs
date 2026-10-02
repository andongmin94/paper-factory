// Run with Electron after starting Vite. This read-only smoke never logs in,
// starts research, or makes a model request. Its profile and evidence are isolated.
import { app, BrowserWindow, dialog } from "electron";
import childProcess from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import path from "node:path";

const output = process.env.PF_DESKTOP_SMOKE_OUTPUT;
if (!output || !path.isAbsolute(output))
  throw new Error("PF_DESKTOP_SMOKE_OUTPUT must be an absolute evidence directory.");
await mkdir(output, { recursive: true });
app.setPath("userData", path.join(output, "electron-profile"));
process.env.PF_HOME = path.join(output, "workspace");
process.env.ELECTRON_RENDERER_URL = "http://127.0.0.1:5173/";
const messages = [];
let failed = false;
let captured = false;
let screenshot;
const record = {
  kind: "read-only-electron-smoke",
  electron: process.versions.electron,
  node: process.versions.node,
  temporaryProfile: process.env.PF_HOME,
  modelCalls: 0,
  accountActions: 0,
  runtime: null,
  health: null,
  connection: null,
  security: null,
  title: null,
  screenshot: null,
  gracefulQuit: false,
};
const spawn = childProcess.spawn;
childProcess.spawn = (...args) => {
  const child = spawn(...args);
  if (args[1]?.includes("paper_factory.desktop")) {
    let diagnostic = "";
    child.stderr?.on("data", (chunk) => {
      diagnostic = (diagnostic + chunk.toString()).slice(-8192);
    });
    child.once("exit", (code, signal) => {
      record.backendExit = { code, signal };
      if (code !== 0 || signal !== null) {
        failed = true;
        messages.push({ backendExitError: diagnostic });
      }
    });
  }
  return child;
};
syncBuiltinESMExports();

// Prevent a visible window even when production ready-to-show calls show().
BrowserWindow.prototype.show = function () {};
dialog.showErrorBox = (title, content) => {
  failed = true;
  messages.push({ title, content });
  setTimeout(() => app.quit(), 0);
};
dialog.showMessageBox = async (options) => {
  failed = true;
  messages.push({ title: options.title, content: options.message });
  return { response: 0, checkboxChecked: false };
};

app.on("browser-window-created", (_event, window) => {
  window.webContents.on("console-message", (details) => {
    if (details.level === "error") messages.push({ rendererError: details.message });
  });
  window.webContents.once("did-finish-load", async () => {
    try {
      const state = await window.webContents.executeJavaScript(`(async () => {
        const runtime = await window.paperFactory.getRuntimeInfo();
        const health = await window.paperFactory.request('GET', '/api/health');
        const connection = await window.paperFactory.request('GET', '/api/agent/connection');
        let shutdownBlocked = false, externalBlocked = false, networkBlocked = false;
        try { await window.paperFactory.request('POST', '/api/desktop/shutdown', {}); } catch { shutdownBlocked = true; }
        try { await window.paperFactory.openExternal('https://example.com/'); } catch { externalBlocked = true; }
        try { await fetch('https://example.com/'); } catch { networkBlocked = true; }
        return {runtime, health, connection, security:{shutdownBlocked,externalBlocked,networkBlocked,nodeUnavailable:typeof require === 'undefined'}, title:document.title};
      })()`);
      Object.assign(record, state);
      if (
        state.connection.status === "authenticated" ||
        state.connection.logged_in === true ||
        !Object.values(state.security).every(Boolean)
      )
        throw new Error("Isolated session/security smoke failed");
      await new Promise((resolve) => setTimeout(resolve, 700));
      screenshot = path.join(output, "window.png");
      const image = await window.webContents.capturePage();
      await writeFile(screenshot, image.toPNG());
      record.screenshot = screenshot;
      record.bodyText = await window.webContents.executeJavaScript("document.body.innerText");
      record.views = {};
      for (const label of ["진행 현황", "논문 보관함"]) {
        await window.webContents.executeJavaScript(
          `(() => { const button = [...document.querySelectorAll('button')].find(item => item.innerText.trim() === ${JSON.stringify(label)}); if (!button) throw new Error('View button unavailable'); button.click(); })()`,
        );
        await new Promise((resolve) => setTimeout(resolve, 350));
        const filename = path.join(output, label === "진행 현황" ? "progress.png" : "library.png");
        await writeFile(filename, (await window.webContents.capturePage()).toPNG());
        record.views[label] = {
          screenshot: filename,
          text: await window.webContents.executeJavaScript("document.body.innerText"),
        };
      }
      captured = true;
    } catch (error) {
      failed = true;
      messages.push({ error: String(error) });
    } finally {
      app.quit();
    }
  });
});

app.once("will-quit", (event) => {
  event.preventDefault();
  record.gracefulQuit = captured && !failed;
  // The main before-quit gate has already awaited authenticated shutdown + exit.
  void writeFile(
    path.join(output, "result.json"),
    JSON.stringify({ ...record, messages }, null, 2),
  ).then(() => app.exit(failed ? 1 : 0));
});

// No production test flags: import the exact compiled main and observe its window.
await import(new URL("../dist/electron/main.js", import.meta.url));
