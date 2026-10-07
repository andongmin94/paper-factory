import { _electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";
import { access, mkdir, mkdtemp, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { basename, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import type { AppSnapshot, PaperFactoryApi } from "../src/shared/contracts";
import type { ManuscriptReview, ResearchSnapshot, StudyReview } from "../src/shared/research";
import type { OpenDialogOptions, SaveDialogOptions } from "electron";

declare global {
  interface Window {
    paperFactory: PaperFactoryApi;
  }
}

const desktopRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const syntheticQualityCriterion = { passed: true, reason: "실제 연구 판단이 아닌 UI 검증용 합성 승인입니다." };
const approvedStudyReview: StudyReview = {
  accepted: true, issues: [], question: syntheticQualityCriterion, contribution: syntheticQualityCriterion,
  literature: syntheticQualityCriterion, comparison: syntheticQualityCriterion, sampling: syntheticQualityCriterion,
  feasibility: syntheticQualityCriterion, selected_sources: [1, 2].map(index => ({
    source_id: `fixture-source-${index}`, excerpt_index: 0, relevance: "실제 논문이 아닌 UI fixture 근거 선택입니다.",
  })),
};
const approvedManuscriptReview: ManuscriptReview = {
  accepted: true, issues: [], checks: ["UI fixture 승인 상태"], contribution: syntheticQualityCriterion,
  literature: syntheticQualityCriterion, interpretation: syntheticQualityCriterion, presentation: syntheticQualityCriterion,
};
function researchFixture(id: string) {
  return { parentResearchId: null, rootResearchId: id, redesignAttempt: 0, followupResearchId: null, improvementAvailable: false };
}
const workspacePanels = { 연결: "connection", "새 연구": "research", 결과: "results" } as const;
type WorkspaceView = keyof typeof workspacePanels;

async function expectView(page: Page, selected: WorkspaceView) {
  for (const [name, id] of Object.entries(workspacePanels)) {
    const active = name === selected;
    const tab = page.getByRole("tab", { name, exact: true });
    const panel = page.locator(`#${id}-panel`);
    await expect(tab).toBeEnabled();
    await expect(tab).toHaveAttribute("aria-selected", String(active));
    await expect(tab).toHaveAttribute("aria-controls", `${id}-panel`);
    await expect(panel).toBeAttached();
    await expect(panel).toHaveAttribute("role", "tabpanel");
    await expect(panel).toHaveAttribute("aria-labelledby", `workspace-tab-${id}`);
    await expect(panel).toHaveJSProperty("hidden", !active);
    if (active) await expect(panel).toBeVisible();
    else await expect(panel).toBeHidden();
  }
}

async function selectView(page: Page, view: WorkspaceView) {
  await page.getByRole("tab", { name: view, exact: true }).click();
  await expectView(page, view);
}

async function launch(dataDir: string) {
  const env: Record<string, string> = Object.fromEntries(
    Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined),
  );
  env.PF_DESKTOP_DATA_DIR = dataDir;
  delete env.ELECTRON_RUN_AS_NODE;
  // Change only window rendering options while loading the genuine main entry.
  // Keeping the launcher beside package.json preserves the real app/runtime paths and version.
  const launcher = join(desktopRoot, `.paper-factory-electron-${randomUUID()}.cjs`);
  await writeFile(launcher, `
const electron = require("electron");
const { registerHooks } = require("node:module");
const entry = ${JSON.stringify(new URL("../dist/main.js", import.meta.url).href)};
registerHooks({ load(url, context, nextLoad) {
  const loaded = nextLoad(url, context);
  if (url !== entry) return loaded;
  const source = loaded.source.toString();
  const pattern = /new BrowserWindow\\(\\{[\\s\\S]*?\\n\\s*\\}\\);/g;
  const constructors = [...source.matchAll(pattern)];
  if (constructors.length !== 1) throw new Error("Expected exactly one production app window constructor.");
  const window = constructors[0][0];
  if (!window.includes("webPreferences: {")) throw new Error("Production app window preferences were not found.");
  const hidden = window.replace("new BrowserWindow({", "new BrowserWindow({ show: false,")
    .replace("webPreferences: {", "webPreferences: { offscreen: true, backgroundThrottling: false,");
  return { ...loaded, source: source.replace(window, hidden) };
} });
import(entry).catch(error => {
  console.error(error);
  electron.app.exit(1);
});
`, { encoding: "utf8", flag: "wx" });
  let electronApp: ElectronApplication | undefined;
  try {
    electronApp = await _electron.launch({ args: [launcher], cwd: desktopRoot, env, timeout: 30_000 });
    await electronApp.firstWindow();
    expect(await electronApp.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().every(window =>
      !window.isVisible() && window.webContents.isOffscreen()))).toBe(true);
    return electronApp;
  } catch (error) {
    await electronApp?.close();
    throw error;
  } finally {
    await rm(launcher, { force: true });
  }
}

async function removeOwnedTemp(dataDir: string) {
  const target = resolve(dataDir);
  if (!target.startsWith(resolve(tmpdir()) + sep) || !basename(target).startsWith("paper-factory-electron-")) {
    throw new Error("Refusing to remove a directory outside the owned Electron test temp root.");
  }
  await rm(target, { recursive: true, force: true });
}

test("connection window uses genuine components and exposes only limited, token-free IPC", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    await expect(page.getByRole("heading", { name: "Paper Factory", exact: true })).toBeVisible();
    await expectView(page, "연결");
    await selectView(page, "새 연구");
    await expect(page.getByRole("heading", { name: "새 연구", exact: true })).toBeVisible();
    const source = page.getByLabel("공개 GitHub 저장소 또는 계정 URL", { exact: true });
    const goal = page.getByLabel("연구 목표", { exact: true });
    const draftSource = "https://github.com/fixture-owner/disconnected-study";
    const draftGoal = "연결 전 입력 보존을 확인하는 합성 연구 목표입니다.";
    await source.fill(draftSource);
    await goal.fill(draftGoal);
    await selectView(page, "결과");
    await expect(page.getByRole("heading", { name: "연구 결과", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "아직 저장된 연구가 없습니다.", exact: true })).toBeVisible();
    await selectView(page, "새 연구");
    await expect(source).toHaveValue(draftSource);
    await expect(goal).toHaveValue(draftGoal);
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
    await selectView(page, "연결");
    const signIn = page.getByRole("button", { name: "Continue with ChatGPT", exact: true });
    await expect(signIn).toBeEnabled();
    await expect(page.getByText("연결 안 됨", { exact: true })).toBeVisible();
    await expect(page.getByText("미확인", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "실제 응답 확인", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "모델 새로고침" })).toBeDisabled();
    await expect(page.getByRole("combobox", { name: "이 계정에서 사용할 수 있는 모델" })).toBeDisabled();

    const rendererSurface = await page.evaluate(() => ({
      process: typeof (globalThis as Record<string, unknown>).process,
      require: typeof (globalThis as Record<string, unknown>).require,
      api: Object.keys(window.paperFactory).sort(),
      csp: document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.getAttribute("content"),
    }));
    expect(rendererSurface.process).toBe("undefined");
    expect(rendererSurface.require).toBe("undefined");
    expect(rendererSurface.api).toEqual([
      "addResearchEvidence", "cancel", "cancelResearch", "checkRuntime", "createResearch", "disconnect", "improveResearchWriting", "listPublicRepositories", "onResearchSnapshot", "onSnapshot",
      "openArtifact", "openUsage", "refreshModels", "researchSnapshot", "resumeResearch", "reviseResearchWriting", "saveArtifact", "selectProfile", "showArtifactFolder", "signIn", "snapshot", "verify",
    ]);
    expect(rendererSurface.csp).toContain("script-src 'self'");
    expect(rendererSurface.csp).toContain("object-src 'none'");
    expect(rendererSurface.csp).not.toContain("script-src 'self' 'unsafe-inline'");
    for (const request of [{ id: "invalid", model: "fixture" }, { id: "research-abcdef123456", model: "" }]) {
      const denied = await page.evaluate(async ({ id, model }) => {
        try { await window.paperFactory.reviseResearchWriting(id, model, "fixture-reviewer"); return false; }
        catch { return true; }
      }, request);
      expect(denied).toBe(true);
      expect(await page.evaluate(async ({ id, model }) => {
        try { await window.paperFactory.improveResearchWriting(id, model, "fixture-reviewer"); return false; }
        catch { return true; }
      }, request)).toBe(true);
    }
    for (const request of [{ id: "invalid", artifactId: "export-pdf" }, { id: "research-abcdef123456", artifactId: "unsupported" }]) {
      expect(await page.evaluate(async ({ id, artifactId }) => {
        try { await window.paperFactory.saveArtifact(id, artifactId); return false; }
        catch { return true; }
      }, request)).toBe(true);
    }
    const preferences = await (await electronApp.browserWindow(page)).evaluate((browserWindow) => {
      const settings = browserWindow.webContents.getLastWebPreferences();
      return { contextIsolation: settings.contextIsolation, nodeIntegration: settings.nodeIntegration,
        sandbox: settings.sandbox, webSecurity: settings.webSecurity };
    });
    expect(preferences).toEqual({ contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true });
    const initial = await page.evaluate(() => window.paperFactory.snapshot());
    expect(initial.session).toEqual({ connected: false, sharing: false });
    expect(initial.profiles).toEqual([]);
    expect(initial.models).toEqual([]);
    expect(initial.verification).toBeNull();
    expect(JSON.stringify(initial)).not.toMatch(/access_token|refresh_token|id_token|authorization|bearer/i);
    const buttonStyle = await signIn.evaluate((button) => {
      const style = getComputedStyle(button);
      return { border: style.borderTopWidth, shadow: style.boxShadow };
    });
    expect(buttonStyle.border).toBe("2px");
    expect(buttonStyle.shadow).not.toBe("none");

    const fonts = await page.evaluate(async () => {
      const loaded = await Promise.all([500, 700].map(async (weight) => {
        const faces = await document.fonts.load(`${weight} 14px "Pretendard Variable"`, "연구 작업실 Paper Factory");
        return faces.map((face) => ({ family: face.family, status: face.status }));
      }));
      const sources: string[] = [];
      for (const sheet of document.styleSheets) {
        for (const rule of sheet.cssRules) {
          if (!(rule instanceof CSSFontFaceRule) || !rule.style.fontFamily.includes("Pretendard Variable")) continue;
          const source = rule.style.getPropertyValue("src").match(/url\(["']?([^"')]+)/)?.[1];
          if (source) sources.push(new URL(source, sheet.href ?? location.href).href);
        }
      }
      return {
        loaded,
        family: getComputedStyle(document.documentElement).fontFamily,
        sources,
      };
    });
    expect(fonts.family).toMatch(/^"Pretendard Variable"/);
    for (const faces of fonts.loaded) {
      expect(faces).toHaveLength(1);
      expect(faces[0]).toEqual({ family: "Pretendard Variable", status: "loaded" });
    }
    expect(fonts.sources).toHaveLength(1);
    expect(fonts.sources[0]).toMatch(/^file:\/\/\/.*\/PretendardVariable-[\w-]+\.woff2$/);

    // Use the actual supported IPC method while disconnected; no OAuth or network call is made.
    for (let attempt = 0; attempt < 2; attempt++) {
      const rejected = await page.evaluate(() => window.paperFactory.refreshModels());
      expect(rejected.error?.code).toBe("sign_in_required");
      expect(rejected.busy).toBeNull();
      expect(rejected.verification).toBeNull();
      await expect(page.getByRole("alert")).toContainText("ChatGPT에 로그인해 주세요.");
      await expect(page.getByRole("alert")).toContainText("sign_in_required");
    }
    await page.screenshot({ path: testInfo.outputPath("connection-window.png"), animations: "disabled", fullPage: true });
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
    const blockedInline = await page.evaluate(() => {
      const script = document.createElement("script");
      script.textContent = "window.__paperFactoryCspFixture = true";
      document.head.appendChild(script);
      return (window as Window & { __paperFactoryCspFixture?: boolean }).__paperFactoryCspFixture === true;
    });
    expect(blockedInline).toBe(false);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("credit retry is explicit, research draft models persist, and synthetic busy research keeps navigation available", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const fixtureSnapshot: AppSnapshot = {
    version: "fixture",
    session: { connected: true, sharing: true, profileId: "fixture-a", account: { email: "fixture@example.invalid" } },
    profiles: [
      { id: "fixture-a", label: "Fixture account A", email: "fixture@example.invalid", connected: true, sharing: true },
      { id: "fixture-b", label: "Fixture account B", email: "fixture@example.invalid", connected: true, sharing: true },
    ],
    models: [
      { slug: "fixture-model", displayName: "Fixture model" },
      { slug: "fixture-writer", displayName: "Fixture writer" },
      { slug: "fixture-reviewer", displayName: "Fixture reviewer" },
    ],
    busy: null,
    error: { code: "subscription_sharing_usage_limit_exceeded", message: "테스트용 사용량 한도 오류", action: "usage" },
    verification: null,
  };
  const fixtureResearch: ResearchSnapshot = {
    runtime: { state: "ready", message: "합성 fixture 실행 환경입니다. 실제 런타임 검증이 아닙니다." },
    busy: false,
    cleanupResearchIds: [],
    jobs: [],
    error: null,
  };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect(page.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeVisible();
    await expectView(page, "연결");
    // Let only this owned, disconnected temp app finish startup before replacing its research state.
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state)
      .not.toBe("checking");
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    // Override only this owned fixture process. The normal preload bridge and usage handler remain intact.
    // Fake verification never invokes OAuth, the SDK, or the network; shell interception opens no browser.
    await electronApp.evaluate(async ({ BrowserWindow, ipcMain, shell }, { snapshot, research }) => {
      const fixture = { snapshot, research, verifyCalls: 0, researchCalls: 0, revisions: [] as string[][], openedUrls: [] as string[] };
      (globalThis as typeof globalThis & { __paperFactoryCreditFixture?: typeof fixture }).__paperFactoryCreditFixture = fixture;
      const publish = () => BrowserWindow.getAllWindows()[0]?.webContents.send("connection:changed", fixture.snapshot);
      ipcMain.removeHandler("connection:snapshot");
      ipcMain.handle("connection:snapshot", () => fixture.snapshot);
      ipcMain.removeHandler("research:snapshot");
      ipcMain.handle("research:snapshot", () => fixture.research);
      ipcMain.removeHandler("research:runtime");
      ipcMain.handle("research:runtime", () => fixture.research);
      ipcMain.removeHandler("research:create");
      ipcMain.handle("research:create", () => {
        fixture.researchCalls++;
        return fixture.research;
      });
      ipcMain.removeHandler("research:revise-writing");
      ipcMain.handle("research:revise-writing", (_event, id: string, model: string, reviewer: string) => {
        const job = fixture.research.jobs.find(job => job.id === id);
        if (!job || job.stage !== "exported" || job.status !== "completed" || fixture.research.busy) throw new Error("Unexpected fixture revision");
        fixture.revisions.push([id, model, reviewer]);
        fixture.research = { ...fixture.research, busy: true, jobs: fixture.research.jobs.map(current => current.id === id
          ? { ...current, stage: "analyzed", status: "ready", pipeline: "running", phase: "manuscript", resumeKind: null, manuscriptReview: null, model, reviewerModel: reviewer } : current) };
        BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", fixture.research);
        return fixture.research;
      });
      ipcMain.removeHandler("connection:verify");
      ipcMain.handle("connection:verify", (_event, model: string) => {
        if (model !== "fixture-model") throw new Error("Unexpected fixture model");
        fixture.verifyCalls++;
        publish();
        return fixture.snapshot;
      });
      ipcMain.removeHandler("connection:select-profile");
      ipcMain.handle("connection:select-profile", (_event, profileId: string) => {
        if (!["fixture-a", "fixture-b"].includes(profileId)) throw new Error("Unexpected fixture profile");
        fixture.snapshot = { ...fixture.snapshot, session: { ...fixture.snapshot.session, profileId } };
        publish();
        return fixture.snapshot;
      });
      shell.openExternal = async (url) => { fixture.openedUrls.push(url); };
      publish();
      BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", fixture.research);
    }, { snapshot: fixtureSnapshot, research: fixtureResearch });
    const inspectFixture = () => electronApp!.evaluate(() => {
      const fixture = (globalThis as typeof globalThis & {
        __paperFactoryCreditFixture: { verifyCalls: number; researchCalls: number; revisions: string[][]; openedUrls: string[]; snapshot: AppSnapshot };
      }).__paperFactoryCreditFixture;
      return { verifyCalls: fixture.verifyCalls, researchCalls: fixture.researchCalls,
        revisions: fixture.revisions, openedUrls: fixture.openedUrls, profileId: fixture.snapshot.session.profileId };
    });

    await selectView(page, "새 연구");
    await expect(page.getByText(fixtureResearch.runtime.message, { exact: true })).toBeVisible();
    const source = page.getByLabel("공개 GitHub 저장소 또는 계정 URL", { exact: true });
    const goal = page.getByLabel("연구 목표", { exact: true });
    const writer = page.getByRole("combobox", { name: "작성 모델 (writer)", exact: true });
    const reviewer = page.getByRole("combobox", { name: "리뷰 모델 (reviewer)", exact: true });
    const draftSource = "https://github.com/fixture-owner/synthetic-study";
    const draftGoal = "탭 이동과 모델 선택 보존만 확인합니다. 실제 연구 실행은 하지 않습니다.";
    await source.fill(draftSource);
    await goal.fill(draftGoal);
    await writer.click();
    await page.getByRole("option", { name: "Fixture writer", exact: true }).click();
    await expect(writer).toContainText("Fixture writer");
    await expect(writer).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByRole("listbox")).toHaveCount(0);
    await reviewer.click();
    await expect(reviewer).toHaveAttribute("aria-expanded", "true");
    const reviewerMenuId = await reviewer.getAttribute("aria-controls");
    expect(reviewerMenuId).not.toBeNull();
    const reviewerMenu = page.getByRole("listbox");
    await expect(reviewerMenu).toHaveAttribute("id", reviewerMenuId!);
    await page.screenshot({ path: testInfo.outputPath("reviewer-model-menu.png"), animations: "disabled", fullPage: true });
    await reviewerMenu.getByRole("option", { name: "Fixture reviewer", exact: true }).click();
    await selectView(page, "결과");
    await expect(page.getByRole("heading", { name: "아직 저장된 연구가 없습니다.", exact: true })).toBeVisible();
    await selectView(page, "새 연구");
    await expect(source).toHaveValue(draftSource);
    await expect(goal).toHaveValue(draftGoal);
    await expect(writer).toContainText("Fixture writer");
    await expect(reviewer).toContainText("Fixture reviewer");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeEnabled();
    expect((await inspectFixture()).researchCalls).toBe(0);
    await selectView(page, "연결");

    const confirmation = page.getByRole("checkbox", { name: "ChatGPT에서 크레딧 사용 허용을 켰습니다", exact: true });
    const verify = page.getByRole("button", { name: "실제 응답 확인", exact: true });
    await expect(confirmation).toBeVisible();
    await expect(confirmation).not.toBeChecked();
    await expect(verify).toBeDisabled();
    await expect(page.getByText("사용량 한도에 도달한 후 다른 앱에서 크레딧 사용 허용", { exact: true })).toBeVisible();
    await expect(page.getByRole("alert")).toContainText("ChatGPT 계정 설정을 변경하지 않습니다.");

    await page.getByRole("button", { name: "크레딧 사용 설정" }).click();
    await expect.poll(async () => (await inspectFixture()).openedUrls).toEqual(["https://chatgpt.com/settings/usage"]);
    await expect(confirmation).not.toBeChecked();
    expect((await inspectFixture()).verifyCalls).toBe(0);

    await confirmation.check();
    await expect(confirmation).toBeChecked();
    await expect(verify).toBeEnabled();
    expect((await inspectFixture()).verifyCalls).toBe(0);
    await page.screenshot({ path: testInfo.outputPath("credit-limit-acknowledgement.png"), animations: "disabled", fullPage: true });
    await verify.click();
    await expect.poll(async () => (await inspectFixture()).verifyCalls).toBe(1);
    await expect(confirmation).not.toBeChecked();
    await expect(verify).toBeDisabled();

    await confirmation.check();
    await expect(verify).toBeEnabled();
    await page.getByRole("combobox", { name: "ChatGPT 계정", exact: true }).click();
    await page.getByRole("option", { name: "Fixture account B · fixture@example.invalid", exact: true }).click();
    await expect.poll(async () => (await inspectFixture()).profileId).toBe("fixture-b");
    await expect(confirmation).not.toBeChecked();
    await expect(verify).toBeDisabled();
    expect((await inspectFixture()).verifyCalls).toBe(1);

    await electronApp.evaluate(({ BrowserWindow }) => {
      const fixture = (globalThis as typeof globalThis & {
        __paperFactoryCreditFixture: { snapshot: AppSnapshot };
      }).__paperFactoryCreditFixture;
      fixture.snapshot = { ...fixture.snapshot, error: { code: "network_error", message: "테스트용 연결 오류", action: "retry" } };
      BrowserWindow.getAllWindows()[0]?.webContents.send("connection:changed", fixture.snapshot);
    });
    await expect(confirmation).toHaveCount(0);
    await expect(verify).toBeEnabled();
    await expect(page.getByRole("combobox", { name: "ChatGPT 계정", exact: true })).toBeEnabled();

    // Explicit revision uses the existing selected models through the genuine preload bridge.
    // Only this isolated main-process handler returns synthetic state; it makes no engine/model calls.
    const completedResearch: ResearchSnapshot = { ...fixtureResearch, jobs: [{
      id: "research-abcdef123456", source: draftSource, goal: draftGoal, supportingDocuments: [],
      ...researchFixture("research-abcdef123456"),
      studyReview: approvedStudyReview, manuscriptReview: approvedManuscriptReview,
      model: "fixture-model", reviewerModel: "fixture-model", phase: "idle", pipeline: "completed",
      resumeKind: null,
      stage: "exported", status: "completed", code: null, message: "Synthetic completed paper; no real experiment.",
      updatedAt: "2026-01-01T00:00:00.000Z", artifacts: ["export-pdf", "export-docx", "export-md", "export-tex", "reproducibility"]
        .map(id => ({ id, sha256: "a".repeat(64), size: 18 })),
    }] };
    await electronApp.evaluate(({ BrowserWindow }, research) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryCreditFixture: { research: ResearchSnapshot } }).__paperFactoryCreditFixture;
      fixture.research = research;
      BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", research);
    }, completedResearch);
    await selectView(page, "결과");
    await expect(page.getByRole("button", { name: "Markdown 저장", exact: true })).toBeVisible();
    await page.getByText("재개·보완·원고 수정에 사용할 모델", { exact: true }).click();
    await expect(page.getByRole("combobox", { name: "재개 작성 모델", exact: true })).toContainText("Fixture writer");
    await expect(page.getByRole("combobox", { name: "재개 리뷰 모델", exact: true })).toContainText("Fixture reviewer");
    const revision = page.getByRole("button", { name: "원고 수정", exact: true });
    await expect(revision).toBeEnabled(); expect((await inspectFixture()).revisions).toEqual([]);
    await expect(page.getByRole("button", { name: "연구 준비 재개", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "원고 작성 재개", exact: true })).toHaveCount(0);
    await revision.scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath("completed-paper-revision.png"), animations: "disabled", fullPage: true });
    await revision.click();
    await expect.poll(async () => (await inspectFixture()).revisions).toEqual([["research-abcdef123456", "fixture-writer", "fixture-reviewer"]]);
    await expect(revision).toHaveCount(0);
    await expect(page.getByText("analyzed · ready", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "연구 취소", exact: true })).toBeEnabled();
    await selectView(page, "새 연구");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
    await selectView(page, "연결");

    // This receipt is synthetic UI state, not a live research run or an execution attestation.
    const busyReceipt = "합성 fixture 진행 중 표시입니다. 실제 연구 실행이나 생성된 결과가 아닙니다.";
    const busyResearch: ResearchSnapshot = {
      ...fixtureResearch,
      busy: true,
      jobs: [{ id: "synthetic-busy-receipt", source: draftSource, goal: draftGoal, supportingDocuments: [], studyReview: null, manuscriptReview: null,
        ...researchFixture("synthetic-busy-receipt"),
        model: "fixture-writer", reviewerModel: "fixture-reviewer", phase: "plan", pipeline: "running",
        resumeKind: null,
        stage: "synthetic-ui-fixture", status: "running", code: null, message: busyReceipt,
        updatedAt: "2026-01-01T00:00:00.000Z", artifacts: [] }],
    };
    await electronApp.evaluate(({ BrowserWindow }, research) => {
      const fixture = (globalThis as typeof globalThis & {
        __paperFactoryCreditFixture: { research: ResearchSnapshot };
      }).__paperFactoryCreditFixture;
      fixture.research = research;
      BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", research);
    }, busyResearch);
    await expectView(page, "연결");
    for (const name of ["Continue with ChatGPT", "계정 추가", "연결 해제", "실제 응답 확인", "모델 새로고침", "사용량 확인", "크레딧 사용 설정"]) {
      await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
    }
    await expect(page.getByRole("combobox", { name: "ChatGPT 계정", exact: true })).toBeDisabled();
    await expect(page.getByRole("combobox", { name: "이 계정에서 사용할 수 있는 모델", exact: true })).toBeDisabled();
    await selectView(page, "새 연구");
    for (const input of [source, goal, writer, reviewer]) await expect(input).toBeDisabled();
    await expect(source).toHaveValue(draftSource);
    await expect(goal).toHaveValue(draftGoal);
    await expect(writer).toContainText("Fixture writer");
    await expect(reviewer).toContainText("Fixture reviewer");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "실행 환경 다시 확인", exact: true })).toBeDisabled();
    await page.screenshot({ path: testInfo.outputPath("synthetic-busy-research.png"), animations: "disabled", fullPage: true });
    await selectView(page, "결과");
    await expect(page.getByText(busyReceipt, { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "연구 취소", exact: true })).toBeEnabled();
    await page.screenshot({ path: testInfo.outputPath("synthetic-busy-results.png"), animations: "disabled", fullPage: true });
    await selectView(page, "연결");
    expect((await inspectFixture()).researchCalls).toBe(0);
    expect((await inspectFixture()).verifyCalls).toBe(1);
    expect((await inspectFixture()).openedUrls).toEqual(["https://chatgpt.com/settings/usage"]);
    expect(pageErrors).toEqual([]);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("OS-protected harmless fixture ciphertext decrypts after owned app restart; no live authentication is claimed", async () => {
  test.skip(!["win32", "darwin"].includes(process.platform), "Standalone target OS protection requires Windows or macOS.");
  test.setTimeout(120_000);
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  const fixtureText = "Paper Factory safeStorage test fixture: contains no credentials.";
  const fixturePath = join(dataDir, "safe-storage-fixture.bin");
  let electronApp: ElectronApplication | undefined;
  try {
    electronApp = await test.step("launch first isolated app", () => launch(dataDir));
    const firstPage = await test.step("wait for first isolated window", () => electronApp!.firstWindow());
    await test.step("wait for first app startup to finish before requesting quit", () =>
      expect(firstPage.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeEnabled({ timeout: 60_000 }));
    await expectView(firstPage, "연결");
    const result = await test.step("encrypt harmless fixture with OS safeStorage", () =>
      electronApp!.evaluate(({ app, safeStorage }, text) => ({
        available: safeStorage.isEncryptionAvailable(),
        userData: app.getPath("userData"),
        ciphertext: Array.from(safeStorage.encryptString(text)),
      }), fixtureText));
    expect(result.available).toBe(true);
    expect(resolve(result.userData)).toBe(resolve(dataDir));
    const ciphertext = Buffer.from(result.ciphertext);
    expect(ciphertext.includes(Buffer.from(fixtureText))).toBe(false);
    await test.step("persist harmless fixture ciphertext", () => writeFile(fixturePath, ciphertext));
    await test.step("close first isolated app before restart", () => electronApp!.close());
    electronApp = undefined;

    electronApp = await test.step("restart isolated app with same data", () => launch(dataDir));
    const page = await test.step("wait for restarted isolated window", () => electronApp!.firstWindow());
    await test.step("wait for restarted app startup to finish", () =>
      expect(page.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeEnabled({ timeout: 60_000 }));
    await expectView(page, "연결");
    const stored = await readFile(fixturePath);
    const decrypted = await test.step("decrypt persisted harmless fixture", () =>
      electronApp!.evaluate(({ safeStorage }, bytes) =>
        safeStorage.decryptString(Buffer.from(bytes)), Array.from(stored)));
    expect(decrypted).toBe(fixtureText);
    const snapshot = await page.evaluate(() => window.paperFactory.snapshot());
    expect(snapshot.session.connected).toBe(false);
    expect(snapshot.verification).toBeNull();
  } finally {
    if (electronApp) await test.step("close owned isolated app during cleanup", () => electronApp!.close());
    await removeOwnedTemp(dataDir);
  }
});

test("account URL selects an explicitly public repository through main IPC and survives workspace navigation", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect(page.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeVisible();
    await expectView(page, "연결");
    await electronApp.evaluate(() => {
      globalThis.fetch = async (url) => {
        if (url !== 'https://api.github.com/users/fixture-owner/repos?type=owner&sort=updated&per_page=100') throw new Error('Unexpected fixture endpoint');
        return Response.json([
          { name: 'public-study', private: false, owner: { login: 'fixture-owner' } },
          { name: 'private-study', private: true, owner: { login: 'fixture-owner' } },
        ]);
      };
    });
    await selectView(page, "새 연구");
    const source = page.getByLabel("공개 GitHub 저장소 또는 계정 URL", { exact: true });
    await source.fill('https://github.com/fixture-owner');
    await expect(page.getByRole('button', { name: '연구 시작', exact: true })).toBeDisabled();
    await page.getByRole('button', { name: '공개 저장소 조회', exact: true }).click();
    await page.getByRole('combobox', { name: '연구할 공개 저장소', exact: true }).click();
    await expect(page.getByRole('option', { name: 'private-study', exact: true })).toHaveCount(0);
    await page.getByRole('option', { name: 'public-study', exact: true }).click();
    await expect(source).toHaveValue('https://github.com/fixture-owner/public-study');
    await expect(page.getByRole('button', { name: '공개 저장소 조회', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '연구 시작', exact: true })).toBeDisabled();
    await page.screenshot({ path: testInfo.outputPath("public-repository-research.png"), animations: "disabled", fullPage: true });
    await page.locator("aside.workspace-sidebar").screenshot({ path: testInfo.outputPath("workspace-sidebar.png"), animations: "disabled" });
    await selectView(page, "결과");
    await expect(page.getByRole("heading", { name: "연구 결과", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "아직 저장된 연구가 없습니다.", exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("public-repository-results.png"), animations: "disabled", fullPage: true });
    await selectView(page, "새 연구");
    await expect(source).toHaveValue('https://github.com/fixture-owner/public-study');
    await expect(page.getByRole('button', { name: '연구 시작', exact: true })).toBeDisabled();

    const researchTab = page.getByRole("tab", { name: "새 연구", exact: true });
    const resultsTab = page.getByRole("tab", { name: "결과", exact: true });
    const connectionTab = page.getByRole("tab", { name: "연결", exact: true });
    await researchTab.focus();
    await researchTab.press("ArrowDown");
    await expectView(page, "결과");
    await expect(resultsTab).toBeFocused();
    await resultsTab.press("Home");
    await expectView(page, "연결");
    await expect(connectionTab).toBeFocused();
    await connectionTab.press("End");
    await expectView(page, "결과");
    await expect(resultsTab).toBeFocused();
    await resultsTab.press("ArrowUp");
    await expectView(page, "새 연구");
    await expect(researchTab).toBeFocused();
    await expect(source).toHaveValue('https://github.com/fixture-owner/public-study');

    await page.setViewportSize({ width: 720, height: 640 });
    const sidebar = page.locator("aside.workspace-sidebar");
    await expect(sidebar).toBeVisible();
    const sidebarBeforeScroll = await sidebar.boundingBox();
    expect(sidebarBeforeScroll).not.toBeNull();
    const panelScroll = await page.locator("#research-panel").evaluate((panel) => {
      panel.scrollTop = panel.scrollHeight;
      return panel.scrollTop;
    });
    expect(panelScroll).toBeGreaterThan(0);
    const layout = await page.evaluate(() => {
      const sidebar = document.querySelector("aside.workspace-sidebar")!.getBoundingClientRect();
      const header = document.querySelector(".app-topbar")!.getBoundingClientRect();
      const footer = document.querySelector(".app-statusbar")!.getBoundingClientRect();
      return { width: innerWidth, height: innerHeight, windowScrollX: scrollX,
        bodyScrollWidth: document.body.scrollWidth, bodyClientWidth: document.body.clientWidth,
        documentScrollWidth: document.documentElement.scrollWidth, documentClientWidth: document.documentElement.clientWidth,
        sidebarTop: sidebar.top, sidebarBottom: sidebar.bottom, sidebarHeight: sidebar.height,
        headerBottom: header.bottom, footerTop: footer.top };
    });
    expect(layout.width).toBe(720);
    expect(layout.height).toBe(640);
    expect(layout.windowScrollX).toBe(0);
    expect(layout.bodyScrollWidth).toBeLessThanOrEqual(layout.bodyClientWidth);
    expect(layout.documentScrollWidth).toBeLessThanOrEqual(layout.documentClientWidth);
    expect(layout.sidebarTop).toBeCloseTo(layout.headerBottom, 0);
    expect(layout.sidebarBottom).toBeCloseTo(layout.footerTop, 0);
    expect(layout.sidebarHeight).toBeCloseTo(layout.footerTop - layout.headerBottom, 0);
    expect(layout.sidebarTop).toBeCloseTo(sidebarBeforeScroll!.y, 0);
    expect(layout.sidebarHeight).toBeCloseTo(sidebarBeforeScroll!.height, 0);
    await page.locator("#research-panel").evaluate((panel) => { panel.scrollTop = 0; });
    await page.screenshot({ path: testInfo.outputPath("public-repository-research-720x640.png"), animations: "disabled", fullPage: true });
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("window close and app quit share cleanup; failed evidence keeps the window open and retry closes only after preservation", async () => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  let exited = false;
  const original = Buffer.from('{"synthetic":"partial');
  try {
    await mkdir(join(dataDir, "research")); await mkdir(join(dataDir, "evidence"));
    // Invalid owned index prevents runtime startup; there can be no engine/guest.
    await writeFile(join(dataDir, "research", "jobs.json"), "{}");
    const journal = join(dataDir, "evidence", "connection-checks.jsonl");
    await writeFile(journal, original);
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(() => page.evaluate(() => window.paperFactory.snapshot())).toMatchObject({ error: { code: "evidence_write_failed" } });
    await electronApp.evaluate(({ dialog }) => {
      const fixture = { dialogs: [] as string[], release: undefined as undefined | ((response: number) => void) };
      (globalThis as typeof globalThis & { __shutdownFixture: typeof fixture }).__shutdownFixture = fixture;
      dialog.showMessageBox = (async (...args: unknown[]) => {
        const options = args.at(-1) as { message: string };
        fixture.dialogs.push(options.message);
        const response = await new Promise<number>(resolve => { fixture.release = resolve; });
        return { response, checkboxChecked: false };
      }) as typeof dialog.showMessageBox;
    });
    await electronApp.evaluate(({ app, BrowserWindow }) => {
      BrowserWindow.getAllWindows()[0]!.close(); app.quit(); app.quit();
    });
    await expect.poll(() => electronApp!.evaluate(() =>
      (globalThis as typeof globalThis & { __shutdownFixture: { dialogs: string[] } }).__shutdownFixture.dialogs.length)).toBe(1);
    await expect(page.getByRole("heading", { name: "Paper Factory", exact: true })).toBeVisible();
    expect(await readFile(journal)).toEqual(original);
    await electronApp.evaluate(() => {
      (globalThis as typeof globalThis & { __shutdownFixture: { release: (choice: number) => void } }).__shutdownFixture.release(0);
    });
    await page.waitForTimeout(20);
    await electronApp.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0]!.close());
    await expect.poll(() => electronApp!.evaluate(() =>
      (globalThis as typeof globalThis & { __shutdownFixture: { dialogs: string[] } }).__shutdownFixture.dialogs.length)).toBe(2);
    const preserved = journal + ".original";
    await rename(journal, preserved);
    const closed = new Promise<void>(resolve => electronApp!.once("close", () => { exited = true; resolve(); }));
    await electronApp.evaluate(() => {
      (globalThis as typeof globalThis & { __shutdownFixture: { release: (choice: number) => void } }).__shutdownFixture.release(1);
    });
    await closed;
    expect(await readFile(preserved)).toEqual(original);
    const records = (await readFile(journal, "utf8")).trim().split("\n").map(line => JSON.parse(line));
    expect(records.map(record => record.event)).toEqual(["launch"]);
    expect(await readFile(join(dataDir, "research", "jobs.json"), "utf8")).toBe("{}");
  } finally {
    // This owned fixture cannot start Python because its invalid index blocks restoration.
    if (electronApp && !exited) { electronApp.process().kill(); await new Promise<void>(resolve => electronApp!.process().once("exit", () => resolve())); }
    await removeOwnedTemp(dataDir);
  }
});

type NativeSaveLeaseFixture = {
  dialogs: Array<{ kind: "file" | "directory"; title: string | undefined }>;
  shutdownDialogs: string[];
  releaseSelection?: (destination: string | null) => void;
};

test("production main save lease blocks account and research IPC and waits for the selected file commit before closing the native engine", async ({}, testInfo) => {
  const runtimeRoot = join(desktopRoot, "runtime", `${process.platform}-${process.arch}`);
  const inventoryPath = join(runtimeRoot, "runtime-inventory.json");
  const runtimePresent = await access(inventoryPath).then(() => true, error => {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  });
  test.skip(!runtimePresent, "Requires the built native runtime; absent runtime profiles are checked separately.");
  test.setTimeout(120_000);
  const inventory = JSON.parse(await readFile(inventoryPath, "utf8")) as { executables: { python: string } };
  const python = join(runtimeRoot, ...inventory.executables.python.split("/"));
  const fixtureRoot = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  const dataDir = join(fixtureRoot, "app-data");
  const engineHome = join(dataDir, "engine");
  const exports = join(fixtureRoot, "exports");
  const id = "research-abcdef123456";
  await mkdir(exports);
  let electronApp: ElectronApplication | undefined;
  let exited = false;
  const seed = String.raw`
from pathlib import Path
import sys
from paper_factory.standalone_runtime import OWNER
from paper_factory.workflow_models import Workflow
from paper_factory.autonomous.models import FrozenArtifact
from paper_factory.workspace import Workspace, digest_file, write_json
engine_home = Path(sys.argv[1]).resolve()
engine_home.mkdir(parents=True, exist_ok=False)
write_json(engine_home / "owner.json", OWNER)
identifier = "research-abcdef123456"
ws = Workspace.create(engine_home / "workflows" / identifier)
root = ws.path("research/exports/export-attempt-fixture")
root.mkdir(parents=True)
record = Workflow(id=identifier, project_id="fixture-save-only", goal="Owned synthetic save fixture; no scientific execution.",
                  status="completed", stage="exported", message="Synthetic save test only; no models or experiment.")
files = {
    "export-pdf": ("paper.pdf", b"%PDF-1.4\n% OWNED SYNTHETIC SAVE FIXTURE\n"),
    "export-md": ("paper.md", b"# Synthetic save fixture\n\n![Owned synthetic figure](figure-1.png)\n"),
    "export-tex": ("paper.tex", br"\includegraphics{figure-1.png}"),
    "export-figure-1": ("figure-1.png", b"\x89PNG\r\n\x1a\nOWNED SYNTHETIC SAVE BYTES"),
}
for key, (name, body) in files.items():
    path = root / name
    path.write_bytes(body)
    record.artifacts[key] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(), sha256=digest_file(path), size=path.stat().st_size)
ws.save("workflow", record)
print(record.model_dump_json())
`;
  // The bundled interpreter only seeds this fresh temp workspace. No runner, model, or account is invoked.
  const seedEnv: Record<string, string> = { HOME: fixtureRoot, USERPROFILE: fixtureRoot, APPDATA: fixtureRoot, LOCALAPPDATA: fixtureRoot,
    TEMP: fixtureRoot, TMP: fixtureRoot, PYTHONUTF8: "1", PYTHONDONTWRITEBYTECODE: "1",
    ...(process.env.SystemRoot ? { SystemRoot: process.env.SystemRoot } : {}), ...(process.env.WINDIR ? { WINDIR: process.env.WINDIR } : {}) };
  try {
    const { stdout: originalRecord } = await promisify(execFile)(python, ["-I", "-B", "-c", seed, engineHome],
      { cwd: fixtureRoot, env: seedEnv, timeout: 30_000, windowsHide: true });
    const artifactRoot = join(engineHome, "workflows", id, "research", "exports", "export-attempt-fixture");
    const originals = new Map(await Promise.all(["paper.pdf", "paper.md", "paper.tex", "figure-1.png"].map(async name =>
      [name, await readFile(join(artifactRoot, name))] as const)));
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state, { timeout: 60_000 }).toBe("ready");
    const connection = await page.evaluate(() => window.paperFactory.snapshot());
    expect(connection.session).toEqual({ connected: false, sharing: false });
    expect(connection.profiles).toEqual([]); expect(connection.models).toEqual([]);
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).busy,
      { timeout: 60_000 }).toBe(false);
    const research = await page.evaluate(() => window.paperFactory.researchSnapshot());
    expect(research.busy).toBe(false); expect(research.cleanupResearchIds).toEqual([]);
    expect(research.jobs).toHaveLength(1);
    expect(research.jobs[0]).toMatchObject({ id, pipeline: "completed", stage: "exported", status: "completed", resumeKind: null });
    const journal = join(dataDir, "evidence", "connection-checks.jsonl");
    const originalJournal = await readFile(journal);
    expect(originalJournal.toString("utf8").trim().split("\n").map(line => JSON.parse(line).event)).toEqual(["launch"]);
    await electronApp.evaluate(({ dialog }) => {
      const fixture: NativeSaveLeaseFixture = { dialogs: [], shutdownDialogs: [] };
      (globalThis as typeof globalThis & { __paperFactoryNativeSaveLease: NativeSaveLeaseFixture }).__paperFactoryNativeSaveLease = fixture;
      const choose = (kind: "file" | "directory", title: string | undefined) => {
        fixture.dialogs.push({ kind, title });
        return new Promise<string | null>(resolve => { fixture.releaseSelection = resolve; });
      };
      dialog.showSaveDialog = (async (_window: unknown, options: SaveDialogOptions) => {
        const path = await choose("file", options.title);
        return { canceled: path === null, filePath: path ?? undefined };
      }) as typeof dialog.showSaveDialog;
      dialog.showOpenDialog = (async (_window: unknown, options: OpenDialogOptions) => {
        const path = await choose("directory", options.title);
        return { canceled: path === null, filePaths: path === null ? [] : [path] };
      }) as typeof dialog.showOpenDialog;
      dialog.showMessageBox = (async (_window: unknown, options: { message?: string }) => {
        fixture.shutdownDialogs.push(options.message ?? "Unexpected shutdown dialog");
        return { response: 0, checkboxChecked: false };
      }) as typeof dialog.showMessageBox;
    });
    const inspect = () => electronApp!.evaluate(() => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryNativeSaveLease: NativeSaveLeaseFixture }).__paperFactoryNativeSaveLease;
      return { dialogs: fixture.dialogs, shutdownDialogs: fixture.shutdownDialogs };
    });
    const release = (destination: string | null) => electronApp!.evaluate((_electron, destination) => {
      (globalThis as typeof globalThis & { __paperFactoryNativeSaveLease: NativeSaveLeaseFixture }).__paperFactoryNativeSaveLease.releaseSelection!(destination);
    }, destination);
    await selectView(page, "결과");
    const pdf = page.getByRole("button", { name: "PDF 저장", exact: true });
    await pdf.click();
    await expect.poll(async () => (await inspect()).dialogs).toHaveLength(1);
    // Production main handlers remain intact. Every operation is rejected by saveTask before reaching the SDK or a research controller.
    const rejected = await page.evaluate(async id => {
      const operations = [
        () => window.paperFactory.signIn(), () => window.paperFactory.disconnect(), () => window.paperFactory.selectProfile("fixture-never-created"),
        () => window.paperFactory.refreshModels(), () => window.paperFactory.verify("fixture-never-requested"),
        () => window.paperFactory.createResearch({ source: "https://github.com/fixture-owner/never-fetched", goal: "This operation must be rejected before any account or research request.", model: "fixture", reviewerModel: "fixture" }),
        () => window.paperFactory.resumeResearch(id, "fixture", "fixture"), () => window.paperFactory.reviseResearchWriting(id, "fixture", "fixture"),
        () => window.paperFactory.improveResearchWriting(id, "fixture", "fixture"),
        () => window.paperFactory.saveArtifact(id, "export-pdf"),
      ];
      const failures: string[] = [];
      for (const operation of operations) {
        try { await operation(); failures.push("unexpected-success"); }
        catch (error) { failures.push(String(error)); }
      }
      return failures;
    }, id);
    expect(rejected).toHaveLength(10);
    for (const [index, failure] of rejected.entries()) {
      expect(failure).toContain(index < 5
        ? "결과 파일 저장이 끝난 뒤 계정 작업을 시작하세요."
        : "결과 파일 저장이 끝난 뒤 연구 작업을 시작하세요.");
    }
    expect((await inspect()).dialogs).toHaveLength(1);
    expect(await readFile(journal)).toEqual(originalJournal);
    await release(null); await expect(pdf).toBeEnabled();
    await expect(page.getByRole("tabpanel", { name: "결과", exact: true }).getByText("결과 파일을 저장했습니다.", { exact: true })).toHaveCount(0);
    expect(await readdir(exports)).toEqual([]);

    // Resolve real frozen MD/PNG IDs through Python; only the native folder selection is synthetic.
    await page.getByRole("button", { name: "Markdown 저장", exact: true }).click();
    await expect.poll(async () => (await inspect()).dialogs).toHaveLength(2);
    expect((await inspect()).dialogs[1].kind).toBe("directory");
    await release(exports);
    await expect(page.getByRole("tabpanel", { name: "결과", exact: true }).getByText("결과 파일을 저장했습니다.", { exact: true })).toBeVisible();
    const folders = await readdir(exports);
    expect(folders).toHaveLength(1); expect(folders[0]).toMatch(/^Paper Factory-abcdef123456-md-[a-f0-9]{8}$/);
    for (const name of ["paper.md", "figure-1.png"]) expect(await readFile(join(exports, folders[0], name))).toEqual(originals.get(name));

    // The quit request waits for this pending native chooser and the final atomic file write.
    await pdf.click();
    await expect.poll(async () => (await inspect()).dialogs).toHaveLength(3);
    const destination = join(exports, "paper.pdf");
    const closed = new Promise<void>(resolveClosed => electronApp!.once("close", () => { exited = true; resolveClosed(); }));
    await electronApp.evaluate(({ app, BrowserWindow }) => { BrowserWindow.getAllWindows()[0]!.close(); app.quit(); });
    await expect(page.getByRole("heading", { name: "Paper Factory", exact: true })).toBeVisible();
    expect(exited).toBe(false); expect(await access(destination).then(() => true, () => false)).toBe(false);
    expect(await readFile(journal)).toEqual(originalJournal);
    expect((await inspect()).shutdownDialogs).toEqual([]);
    const closing = await page.evaluate(async id => {
      try { await window.paperFactory.saveArtifact(id, "export-pdf"); return "unexpected-success"; }
      catch (error) { return String(error); }
    }, id);
    expect(closing).toContain("앱 종료를 위해 작업과 기록을 정리하고 있습니다.");
    await page.screenshot({ path: testInfo.outputPath("production-native-save-before-close.png"), animations: "disabled", fullPage: true });
    await release(destination);
    await closed;
    expect(exited).toBe(true); expect(await readFile(destination)).toEqual(originals.get("paper.pdf"));
    for (const [name, bytes] of originals) expect(await readFile(join(artifactRoot, name))).toEqual(bytes);
    expect(await readFile(journal)).toEqual(originalJournal);
    const readRecord = String.raw`from pathlib import Path; import sys; from paper_factory.workflow_models import Workflow; from paper_factory.workspace import Workspace; print(Workspace(Path(sys.argv[1]) / "workflows" / "research-abcdef123456").get("workflow", "research-abcdef123456", Workflow).model_dump_json())`;
    const { stdout: finalRecord } = await promisify(execFile)(python, ["-I", "-B", "-c", readRecord, engineHome],
      { cwd: fixtureRoot, env: seedEnv, timeout: 30_000, windowsHide: true });
    expect(JSON.parse(finalRecord)).toEqual(JSON.parse(originalRecord));
  } finally {
    if (electronApp && !exited) {
      await electronApp.evaluate(() => {
        (globalThis as typeof globalThis & { __paperFactoryNativeSaveLease?: NativeSaveLeaseFixture }).__paperFactoryNativeSaveLease?.releaseSelection?.(null);
      }).catch(() => {});
      await electronApp.close();
    }
    await removeOwnedTemp(fixtureRoot);
  }
});

type SaveFixture = {
  calls: string[][];
  dialogs: Array<{ kind: "file" | "directory"; title: string | undefined; defaultPath: string | undefined; extensions: string[]; properties: string[] }>;
  releaseSelection?: (destination: string | null) => void;
};

test("native artifact chooser cancellation, protected destinations, and portable figure bundles keep the renderer locked until saving settles", async ({}, testInfo) => {
  const fixtureRoot = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  const dataDir = join(fixtureRoot, "app-data");
  const documentsPath = join(fixtureRoot, "exports");
  await mkdir(dataDir); await mkdir(documentsPath);
  let electronApp: ElectronApplication | undefined;
  const id = "research-abcdef123456";
  const formats = [
    { artifactId: "export-pdf", label: "PDF", fileName: "paper.pdf", extension: "pdf" },
    { artifactId: "export-docx", label: "Word", fileName: "paper.docx", extension: "docx" },
    { artifactId: "export-md", label: "Markdown", fileName: "paper.md", extension: "md" },
    { artifactId: "export-tex", label: "LaTeX", fileName: "paper.tex", extension: "tex" },
    { artifactId: "reproducibility", label: "재현 패키지 ZIP", fileName: "reproducibility.zip", extension: "zip" },
  ];
  const connection: AppSnapshot = { version: "fixture", session: { connected: true, sharing: true, profileId: "fixture-a" },
    profiles: [{ id: "fixture-a", label: "Synthetic account", connected: true, sharing: true }],
    models: [{ slug: "fixture-model", displayName: "Synthetic model" }], busy: null, error: null, verification: null };
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 파일 저장 fixture" }, busy: false,
    cleanupResearchIds: [], error: null, jobs: [{ id, source: "https://github.com/fixture-owner/synthetic-save-study",
      ...researchFixture(id),
      goal: "네이티브 파일 선택과 합성 바이트 저장만 검증합니다.", model: "fixture-model", reviewerModel: "fixture-model",
      phase: "idle", pipeline: "completed", stage: "exported", status: "completed", resumeKind: null,
      code: null, message: "Synthetic bytes only; no scientific or model execution.", updatedAt: "2026-01-01T00:00:00.000Z",
      artifacts: formats.map(({ artifactId }) => ({ id: artifactId, sha256: "a".repeat(64), size: 18 })), supportingDocuments: [],
      studyReview: approvedStudyReview, manuscriptReview: approvedManuscriptReview }] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await electronApp.evaluate(({ BrowserWindow, dialog, ipcMain }, { artifactModule, formats, documentsPath, protectedRoot }) => {
      const { saveArtifactWithDialog } = process.getBuiltinModule("module").createRequire(artifactModule)("./artifacts.js");
      const fixture: SaveFixture = { calls: [], dialogs: [] };
      (globalThis as typeof globalThis & { __paperFactorySaveFixture: SaveFixture }).__paperFactorySaveFixture = fixture;
      const choose = (kind: "file" | "directory", options: SaveDialogOptions | OpenDialogOptions) => {
        fixture.dialogs.push({ kind, title: options.title, defaultPath: options.defaultPath,
          extensions: options.filters?.flatMap(filter => filter.extensions) ?? [], properties: options.properties ?? [] });
        return new Promise<string | null>(resolve => { fixture.releaseSelection = resolve; });
      };
      dialog.showSaveDialog = (async (_window: unknown, options: SaveDialogOptions) => {
        const filePath = await choose("file", options);
        return { canceled: filePath === null, filePath: filePath ?? undefined };
      }) as typeof dialog.showSaveDialog;
      dialog.showOpenDialog = (async (_window: unknown, options: OpenDialogOptions) => {
        const parent = await choose("directory", options);
        return { canceled: parent === null, filePaths: parent === null ? [] : [parent] };
      }) as typeof dialog.showOpenDialog;
      // Only artifact resolution is synthetic. Selection and atomic copies use the production helper.
      // This proves UI/preload and chooser/write behavior; the original main saveTask lease is not exercised.
      ipcMain.removeHandler("research:save-artifact");
      ipcMain.handle("research:save-artifact", async (_event, ...args: unknown[]) => {
        const gate = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
        if (args.length !== 2 || typeof args[0] !== "string" || typeof args[1] !== "string") throw new Error("Unexpected synthetic save arguments");
        const [researchId, artifactId] = args;
        const job = gate.research.jobs.find(job => job.id === researchId);
        const format = formats.find(format => format.artifactId === artifactId);
        if (!format || job?.pipeline !== "completed" || !job.artifacts.some(artifact => artifact.id === artifactId)) throw new Error("Unexpected synthetic artifact");
        fixture.calls.push([researchId, artifactId]);
        const body = "OWNED SYNTHETIC " + artifactId;
        const files = [{ name: format.fileName, bytes: Buffer.from(body) }];
        if (["md", "tex"].includes(format.extension)) files.push({ name: "figure-1.png", bytes: Buffer.from("OWNED SYNTHETIC FIGURE") });
        try {
          return await saveArtifactWithDialog({ artifact: { path: protectedRoot + "/" + format.fileName, files },
            artifactId, researchId, documentsPath, protectedRoot,
            chooseFile: (options: SaveDialogOptions) => dialog.showSaveDialog(BrowserWindow.getAllWindows()[0]!, options),
            chooseDirectory: (options: OpenDialogOptions) => dialog.showOpenDialog(BrowserWindow.getAllWindows()[0]!, options) });
        } finally { fixture.releaseSelection = undefined; }
      });
    }, { artifactModule: new URL("../dist/artifacts.js", import.meta.url).href, formats, documentsPath, protectedRoot: dataDir });
    const inspect = () => electronApp!.evaluate(() => {
      const fixture = (globalThis as typeof globalThis & { __paperFactorySaveFixture: SaveFixture }).__paperFactorySaveFixture;
      return { calls: fixture.calls, dialogs: fixture.dialogs };
    });
    const releaseSelection = (destination: string | null) => electronApp!.evaluate((_electron, destination) => {
      (globalThis as typeof globalThis & { __paperFactorySaveFixture: SaveFixture }).__paperFactorySaveFixture.releaseSelection!(destination);
    }, destination);
    await selectView(page, "새 연구");
    await page.getByLabel("공개 GitHub 저장소 또는 계정 URL", { exact: true }).fill("https://github.com/fixture-owner/synthetic-save-study");
    await page.getByLabel("연구 목표", { exact: true }).fill("저장 중 연구와 계정 작업 잠금을 확인하는 합성 목표입니다.");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeEnabled();
    await selectView(page, "결과");
    const results = page.getByRole("tabpanel", { name: "결과", exact: true });
    const success = results.getByText("결과 파일을 저장했습니다.", { exact: true });
    expect(await inspect()).toEqual({ calls: [], dialogs: [] });
    const markdown = page.getByRole("button", { name: "Markdown 저장", exact: true });
    await markdown.click();
    await expect.poll(async () => (await inspect()).dialogs).toHaveLength(1);
    for (const { label } of formats) await expect(page.getByRole("button", { name: label + " 저장", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "원고 수정", exact: true })).toBeDisabled();
    await expect(page.getByLabel("저장 파일 경로", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath("native-save-pending.png"), animations: "disabled", fullPage: true });
    await selectView(page, "연결");
    for (const name of ["Continue with ChatGPT", "계정 추가", "연결 해제", "실제 응답 확인"]) {
      await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
    }
    await expect(page.getByRole("combobox", { name: "ChatGPT 계정", exact: true })).toBeDisabled();
    await selectView(page, "새 연구");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
    await releaseSelection(null);
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeEnabled();
    await selectView(page, "결과");
    await expect(markdown).toBeEnabled(); await expect(success).toHaveCount(0);
    await expect(results.getByRole("alert")).toHaveCount(0);
    expect(await readdir(documentsPath)).toEqual([]);

    // A rejected destination returns control without a success notice or an app-data write.
    const pdf = page.getByRole("button", { name: "PDF 저장", exact: true });
    await pdf.click();
    await expect.poll(async () => (await inspect()).dialogs).toHaveLength(2);
    await releaseSelection(join(dataDir, "paper.pdf"));
    await expect(results.getByRole("alert")).toContainText("선택한 위치의 접근 권한과 남은 공간");
    await expect(pdf).toBeEnabled(); await expect(success).toHaveCount(0);
    expect(await readdir(dataDir)).not.toContain("paper.pdf");

    for (const [index, format] of formats.entries()) {
      const before = await readdir(documentsPath);
      await page.getByRole("button", { name: format.label + " 저장", exact: true }).click();
      await expect.poll(async () => (await inspect()).dialogs).toHaveLength(index + 3);
      const chooser = (await inspect()).dialogs.at(-1)!;
      const bundle = ["md", "tex"].includes(format.extension);
      expect(chooser.kind).toBe(bundle ? "directory" : "file");
      expect(chooser.properties).toContain("dontAddToRecent");
      if (bundle) {
        expect(chooser.defaultPath).toBe(documentsPath);
        expect(chooser.properties).toContain("openDirectory");
        await releaseSelection(documentsPath);
      } else {
        expect(chooser.defaultPath).toBe(join(documentsPath, format.fileName));
        expect(chooser.extensions).toEqual([format.extension]);
        await releaseSelection(join(documentsPath, format.fileName));
      }
      await expect(success).toBeVisible();
      await expect(results.getByRole("alert")).toHaveCount(0);
      await expect(page.getByRole("button", { name: format.label + " 저장", exact: true })).toBeEnabled();
      const added = (await readdir(documentsPath)).filter(name => !before.includes(name));
      expect(added).toHaveLength(1);
      const destination = bundle ? join(documentsPath, added[0], format.fileName) : join(documentsPath, added[0]);
      expect(await readFile(destination)).toEqual(Buffer.from("OWNED SYNTHETIC " + format.artifactId));
      if (bundle) {
        expect(added[0]).toMatch(new RegExp(`^Paper Factory-abcdef123456-${format.extension}-[a-f0-9]{8}$`));
        expect((await readdir(join(documentsPath, added[0]))).sort()).toEqual(["figure-1.png", format.fileName].sort());
        expect(await readFile(join(documentsPath, added[0], "figure-1.png"))).toEqual(Buffer.from("OWNED SYNTHETIC FIGURE"));
      }
    }
    expect((await inspect()).calls).toEqual([[id, "export-md"], [id, "export-pdf"], ...formats.map(format => [id, format.artifactId])]);
    expect(await electronApp.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls)).toEqual([]);
    // A cancellation after a completed save clears the old success notice too.
    await pdf.click();
    await expect.poll(async () => (await inspect()).dialogs).toHaveLength(8);
    await expect(success).toHaveCount(0); await releaseSelection(null);
    await expect(pdf).toBeEnabled(); await expect(success).toHaveCount(0);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(fixtureRoot);
  }
});

type GateFixture = {
  connection: AppSnapshot;
  research: ResearchSnapshot;
  cancelledIds: string[];
  forbiddenCalls: string[];
  releaseCleanup?: () => void;
};

async function installGateFixture(electronApp: ElectronApplication, connection: AppSnapshot, research: ResearchSnapshot) {
  await electronApp.evaluate(({ BrowserWindow, ipcMain }, { connection, research }) => {
    // This owned process exercises the actual renderer/preload with synthetic state.
    // Account, model, and scientific handlers are replaced so no live request can occur.
    const fixture: GateFixture = { connection, research, cancelledIds: [], forbiddenCalls: [] };
    (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture = fixture;
    const publish = () => {
      const contents = BrowserWindow.getAllWindows()[0]?.webContents;
      contents?.send("connection:changed", fixture.connection);
      contents?.send("research:changed", fixture.research);
    };
    for (const channel of ["connection:snapshot", "research:snapshot", "research:cancel", "research:runtime",
      "connection:sign-in", "connection:select-profile", "connection:disconnect", "connection:models", "connection:verify",
      "research:create", "research:resume", "research:revise-writing", "research:improve-writing", "research:add-evidence"]) ipcMain.removeHandler(channel);
    ipcMain.handle("connection:snapshot", () => fixture.connection);
    ipcMain.handle("research:snapshot", () => fixture.research);
    ipcMain.handle("research:runtime", () => fixture.research);
    ipcMain.handle("research:cancel", async (_event, id: string) => {
      if (!fixture.research.cleanupResearchIds.includes(id)) throw new Error("Unexpected synthetic cleanup id");
      fixture.cancelledIds.push(id);
      await new Promise<void>(resolve => { fixture.releaseCleanup = resolve; });
      fixture.research = { ...fixture.research, busy: false, cleanupResearchIds: [], error: null,
        jobs: fixture.research.jobs.map(job => job.id === id
          ? { ...job, status: "cancelled", code: "CANCELLED", message: "합성 정리 확인 완료", resumeKind: "preparation" as const } : job) };
      publish();
      return fixture.research;
    });
    for (const channel of ["connection:sign-in", "connection:select-profile", "connection:disconnect", "connection:models", "connection:verify",
      "research:create", "research:resume", "research:revise-writing", "research:improve-writing", "research:add-evidence"]) {
      ipcMain.handle(channel, () => { fixture.forbiddenCalls.push(channel); throw new Error("A locked fixture action was invoked"); });
    }
    publish();
  }, { connection, research });
}

test("unconfirmed cleanup is retried without login or ready runtime while account and new research actions stay locked", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const id = "research-abcdef123456";
  const connection: AppSnapshot = { version: "fixture", session: { connected: false, sharing: false },
    profiles: [{ id: "fixture-a", label: "Synthetic disconnected account", connected: false, sharing: false }],
    models: [], busy: null, error: null, verification: null };
  const research: ResearchSnapshot = { runtime: { state: "unavailable", message: "합성 런타임 실패" }, busy: true,
    cleanupResearchIds: [id], error: { code: "CLEANUP_UNCONFIRMED", message: "합성 정리 미확인", action: "retry" },
    jobs: [{ id, source: "https://github.com/fixture-owner/synthetic-study", goal: "합성 정리 복구만 검증합니다.",
      ...researchFixture(id),
      model: "", reviewerModel: "", phase: "idle", pipeline: "paused", stage: "planned", status: "cancelled",
      resumeKind: null,
      code: "CLEANUP_UNCONFIRMED", message: "합성 작업자는 실행하지 않았습니다.", updatedAt: new Date().toISOString(),
      artifacts: [], supportingDocuments: [], studyReview: null, manuscriptReview: null }] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await expect(page.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "계정 추가", exact: true })).toBeDisabled();
    await expect(page.getByRole("combobox", { name: "ChatGPT 계정", exact: true })).toBeDisabled();
    await selectView(page, "새 연구");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "실행 환경 다시 확인", exact: true })).toBeDisabled();
    await selectView(page, "결과");
    const retry = page.getByRole("button", { name: "정리 다시 확인", exact: true });
    await expect(retry).toBeEnabled();
    await expect(page.getByText("실험 종료와 기록 보존을 확인해야 새 연구와 계정 변경을 할 수 있습니다. 로그인 없이 정리 확인을 다시 시도할 수 있습니다.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "연구 준비 재개", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "원고 작성 재개", exact: true })).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath("synthetic-cleanup-retry.png"), animations: "disabled", fullPage: true });
    await retry.click();
    await expect(page.getByRole("button", { name: "정리 확인 중…", exact: true })).toBeDisabled();
    await expect.poll(() => electronApp!.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.cancelledIds)).toEqual([id]);
    await selectView(page, "연결");
    await expect(page.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeDisabled();
    await electronApp.evaluate(() => {
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.releaseCleanup!();
    });
    await expect(page.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeEnabled();
    await expect(page.getByRole("combobox", { name: "ChatGPT 계정", exact: true })).toBeEnabled();
    await selectView(page, "결과");
    await expect(page.getByRole("button", { name: "정리 다시 확인", exact: true })).toHaveCount(0);
    await expect(page.getByText("합성 정리 확인 완료", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "연구 준비 재개", exact: true })).toBeDisabled();
    await selectView(page, "새 연구");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
    const calls = await electronApp.evaluate(() => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      return { cancelledIds: fixture.cancelledIds, forbiddenCalls: fixture.forbiddenCalls, runtime: fixture.research.runtime.state };
    });
    expect(calls).toEqual({ cancelledIds: [id], forbiddenCalls: [], runtime: "unavailable" });
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("account selection and disconnection busy events lock model and research actions until the account operation settles", async () => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const connection: AppSnapshot = { version: "fixture", session: { connected: true, sharing: true, profileId: "fixture-a" },
    profiles: ["a", "b"].map(id => ({ id: `fixture-${id}`, label: `Synthetic account ${id}`, connected: true, sharing: true })),
    models: [{ slug: "fixture-model", displayName: "Synthetic model" }], busy: null, error: null, verification: null };
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 실행 환경" }, busy: false,
    cleanupResearchIds: [], jobs: [], error: null };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await selectView(page, "새 연구");
    await page.getByLabel("공개 GitHub 저장소 또는 계정 URL", { exact: true }).fill("https://github.com/fixture-owner/synthetic-study");
    await page.getByLabel("연구 목표", { exact: true }).fill("계정 작업 잠금만 확인하는 합성 목표입니다.");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeEnabled();
    for (const [busy, label] of [["select-profile", "선택한 ChatGPT 계정으로 전환하고 있습니다."], ["disconnect", "이 계정의 연결을 해제하고 있습니다."]] as const) {
      await electronApp.evaluate(({ BrowserWindow }, busy) => {
        const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
        fixture.connection = { ...fixture.connection, busy };
        BrowserWindow.getAllWindows()[0]?.webContents.send("connection:changed", fixture.connection);
      }, busy);
      await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
      await expect(page.getByRole("combobox", { name: "작성 모델 (writer)", exact: true })).toBeDisabled();
      await selectView(page, "연결");
      await expect(page.getByText(label, { exact: true })).toBeVisible();
      for (const name of ["Continue with ChatGPT", "계정 추가", "연결 해제", "실제 응답 확인"]) {
        await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
      }
      await expect(page.getByRole("button", { name: "모델 새로고침" })).toBeDisabled();
      await expect(page.getByRole("combobox", { name: "ChatGPT 계정", exact: true })).toBeDisabled();
      await expect(page.getByRole("button", { name: "취소", exact: true })).toHaveCount(0);
      await electronApp.evaluate(({ BrowserWindow }) => {
        const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
        fixture.connection = { ...fixture.connection, busy: null };
        BrowserWindow.getAllWindows()[0]?.webContents.send("connection:changed", fixture.connection);
      });
      await expect(page.getByRole("button", { name: "연결 해제", exact: true })).toBeEnabled();
      await selectView(page, "새 연구");
      await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeEnabled();
    }
    expect(await electronApp.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls)).toEqual([]);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("resume actions follow authoritative preparation and authoring kinds and never appear for blocked or ambiguous science", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const connection: AppSnapshot = { version: "fixture", session: { connected: true, sharing: true, profileId: "fixture-a" },
    profiles: [{ id: "fixture-a", label: "Synthetic account", connected: true, sharing: true }],
    models: [{ slug: "fixture-model", displayName: "Synthetic model" }], busy: null, error: null, verification: null };
  const base: Omit<ResearchSnapshot["jobs"][number], "id" | "source" | "resumeKind" | keyof ReturnType<typeof researchFixture>> = {
    goal: "재개 화면과 명시적 클릭만 확인하는 합성 작업입니다.", model: "fixture-model", reviewerModel: "fixture-model",
    phase: "idle", pipeline: "paused", stage: "planned", status: "cancelled", code: "CANCELLED", message: null,
    updatedAt: "2026-01-01T00:00:00.000Z", artifacts: [], supportingDocuments: [], studyReview: null, manuscriptReview: null,
  };
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 재개 fixture" }, busy: false,
    cleanupResearchIds: [], error: null, jobs: [
      { ...base, ...researchFixture("research-111111111111"), id: "research-111111111111", source: "https://github.com/fixture-owner/preparation-study", resumeKind: "preparation" },
      { ...base, ...researchFixture("research-222222222222"), id: "research-222222222222", source: "https://github.com/fixture-owner/authoring-study", stage: "analyzed", resumeKind: "authoring" },
      { ...base, ...researchFixture("research-333333333333"), id: "research-333333333333", source: "https://github.com/fixture-owner/control-failure", pipeline: "failed", stage: "analyzed",
        status: "blocked", code: "SCIENTIFIC_CONTROL_FAILED", resumeKind: null },
      { ...base, ...researchFixture("research-444444444444"), id: "research-444444444444", source: "https://github.com/fixture-owner/ambiguous-execution", pipeline: "failed",
        status: "failed", code: "RUN_INTERRUPTED", resumeKind: null },
      { ...base, ...researchFixture("research-555555555555"), id: "research-555555555555", source: "https://github.com/fixture-owner/unconfirmed-cleanup",
        code: "CLEANUP_UNCONFIRMED", resumeKind: null },
    ] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await electronApp.evaluate(({ BrowserWindow, ipcMain }) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      const resumeCalls: string[][] = [];
      (globalThis as typeof globalThis & { __paperFactoryResumeCalls: string[][] }).__paperFactoryResumeCalls = resumeCalls;
      ipcMain.removeHandler("research:resume");
      ipcMain.handle("research:resume", (_event, id: string, model: string, reviewerModel: string) => {
        const job = fixture.research.jobs.find(job => job.id === id);
        if (!job?.resumeKind || fixture.research.busy || [model, reviewerModel].some(model => model !== "fixture-model")) {
          throw new Error("Unexpected synthetic resume");
        }
        resumeCalls.push([id, model, reviewerModel]);
        fixture.research = { ...fixture.research, busy: true, jobs: fixture.research.jobs.map(current => current.id === id
          ? { ...current, pipeline: "running", phase: current.resumeKind === "authoring" ? "manuscript" : "plan", resumeKind: null } : current) };
        BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", fixture.research);
        return fixture.research;
      });
    });
    const inspectCalls = () => electronApp!.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryResumeCalls: string[][] }).__paperFactoryResumeCalls);
    await selectView(page, "결과");
    const preparation = page.getByRole("article", { name: "preparation-study", exact: true });
    const authoring = page.getByRole("article", { name: "authoring-study", exact: true });
    await expect(preparation.getByRole("button", { name: "연구 준비 재개", exact: true })).toBeEnabled();
    await expect(authoring.getByRole("button", { name: "원고 작성 재개", exact: true })).toBeEnabled();
    for (const name of ["control-failure", "ambiguous-execution", "unconfirmed-cleanup"]) {
      const job = page.getByRole("article", { name, exact: true });
      await expect(job.getByRole("button", { name: "연구 준비 재개", exact: true })).toHaveCount(0);
      await expect(job.getByRole("button", { name: "원고 작성 재개", exact: true })).toHaveCount(0);
    }
    expect(await inspectCalls()).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("synthetic-resume-kinds.png"), animations: "disabled", fullPage: true });
    await preparation.getByRole("button", { name: "연구 준비 재개", exact: true }).click();
    await expect.poll(inspectCalls).toEqual([["research-111111111111", "fixture-model", "fixture-model"]]);
    await expect(preparation.getByRole("button", { name: "연구 취소", exact: true })).toBeEnabled();
    await expect(authoring.getByRole("button", { name: "원고 작성 재개", exact: true })).toBeDisabled();
    await electronApp.evaluate(({ BrowserWindow }, research) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      fixture.research = research;
      BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", research);
    }, research);
    await expect(authoring.getByRole("button", { name: "원고 작성 재개", exact: true })).toBeEnabled();
    await authoring.getByRole("button", { name: "원고 작성 재개", exact: true }).click();
    await expect.poll(inspectCalls).toEqual([
      ["research-111111111111", "fixture-model", "fixture-model"], ["research-222222222222", "fixture-model", "fixture-model"],
    ]);
    await expect(authoring).toContainText("원고 작성 (manuscript)");
    await expect(authoring.getByRole("button", { name: "원고 작성 재개", exact: true })).toHaveCount(0);
    expect(await electronApp.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls)).toEqual([]);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("held manuscript improvement uses selected models and respects authorization and busy locks", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const id = "research-abcdef123456";
  const connection: AppSnapshot = { version: "fixture", session: { connected: true, sharing: true, profileId: "fixture-a" },
    profiles: [{ id: "fixture-a", label: "Synthetic account", connected: true, sharing: true }],
    models: [{ slug: "fixture-writer", displayName: "Synthetic writer" }, { slug: "fixture-reviewer", displayName: "Synthetic reviewer" }],
    busy: null, error: null, verification: null };
  const base: ResearchSnapshot["jobs"][number] = { ...researchFixture(id), id,
    source: "https://github.com/fixture-owner/improvement-eligible", goal: "보류 원고 보완 요청만 검증하는 합성 UI 연구입니다.",
    model: "fixture-writer", reviewerModel: "fixture-reviewer", phase: "manuscript-review", pipeline: "paused",
    stage: "analyzed", status: "blocked", code: "MANUSCRIPT_REJECTED", message: "기존 심사 기록을 보존한 합성 원고입니다.",
    resumeKind: null, improvementAvailable: true, updatedAt: "2026-01-01T00:00:00.000Z", artifacts: [], supportingDocuments: [],
    studyReview: approvedStudyReview, manuscriptReview: { ...approvedManuscriptReview, accepted: false,
      issues: ["합성 검토: 새로운 보완 판단을 요청해야 합니다."],
      contribution: { passed: false, reason: "합성 보류 판단: 기존 기록에 구조화된 보완 판단이 없습니다." } } };
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 보류 원고 보완 fixture" }, busy: false,
    cleanupResearchIds: [], error: null, jobs: [base,
      { ...base, ...researchFixture("research-111111111111"), id: "research-111111111111", source: "https://github.com/fixture-owner/improvement-unavailable" },
      { ...base, ...researchFixture("research-222222222222"), id: "research-222222222222", source: "https://github.com/fixture-owner/completed-draft",
        improvementAvailable: true, pipeline: "completed", stage: "exported", status: "completed", code: null },
    ] };
  type ImprovementFixture = { calls: string[][]; release?: () => void };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await electronApp.evaluate(({ BrowserWindow, ipcMain }) => {
      const gate = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      const improvement: ImprovementFixture = { calls: [] };
      (globalThis as typeof globalThis & { __paperFactoryImprovementFixture: ImprovementFixture }).__paperFactoryImprovementFixture = improvement;
      ipcMain.removeHandler("research:improve-writing");
      ipcMain.handle("research:improve-writing", async (_event, id: string, model: string, reviewerModel: string) => {
        const job = gate.research.jobs.find(job => job.id === id);
        if (!job?.improvementAvailable || gate.research.busy || !gate.connection.session.connected || !gate.connection.session.sharing
            || model !== "fixture-writer" || reviewerModel !== "fixture-reviewer") throw new Error("Unexpected synthetic improvement request");
        improvement.calls.push([id, model, reviewerModel]);
        gate.research = { ...gate.research, busy: true, jobs: gate.research.jobs.map(job => job.id === id
          ? { ...job, improvementAvailable: false, pipeline: "running", phase: "manuscript-review" } : job) };
        BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", gate.research);
        await new Promise<void>(resolve => { improvement.release = resolve; });
        // The real controller acknowledges the start while its background job
        // remains busy. A delayed acknowledgement locks all local actions.
        return gate.research;
      });
    });
    const inspect = () => electronApp!.evaluate(() => ({
      calls: (globalThis as typeof globalThis & { __paperFactoryImprovementFixture: ImprovementFixture }).__paperFactoryImprovementFixture.calls,
      forbiddenCalls: (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls,
    }));
    const changeGate = (sharing: boolean, busy: boolean) => electronApp!.evaluate(({ BrowserWindow }, { sharing, busy }) => {
      const gate = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      gate.connection = { ...gate.connection, session: { ...gate.connection.session, sharing } };
      gate.research = { ...gate.research, busy };
      BrowserWindow.getAllWindows()[0]?.webContents.send("connection:changed", gate.connection);
      BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", gate.research);
    }, { sharing, busy });
    await selectView(page, "결과");
    await page.getByText("재개·보완·원고 수정에 사용할 모델", { exact: true }).click();
    await page.getByRole("combobox", { name: "재개 리뷰 모델", exact: true }).click();
    await page.getByRole("option", { name: "Synthetic reviewer", exact: true }).click();
    const held = page.getByRole("article", { name: "improvement-eligible", exact: true });
    const improve = held.getByRole("button", { name: "심사·보완 이어가기", exact: true });
    await expect(improve).toBeEnabled();
    await expect(held).toContainText("추가 측정이 필요하면 별도 연구를 설계하고 적합성 검토부터 진행합니다.");
    await expect(page.getByRole("article", { name: "improvement-unavailable", exact: true }).getByRole("button", { name: "심사·보완 이어가기", exact: true })).toHaveCount(0);
    await expect(page.getByRole("article", { name: "completed-draft", exact: true }).getByRole("button", { name: "심사·보완 이어가기", exact: true })).toHaveCount(0);
    await changeGate(false, false); await expect(improve).toBeDisabled();
    await changeGate(true, true); await expect(improve).toBeDisabled();
    expect((await inspect()).calls).toEqual([]);
    await changeGate(true, false); await expect(improve).toBeEnabled();
    await held.evaluate(element => element.scrollIntoView({ block: "start" }));
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    const captureWindow = await electronApp.browserWindow(page);
    const png = await captureWindow.evaluate(async window => {
      const image = await window.webContents.capturePage(undefined, { stayHidden: true });
      if (window.isVisible() || image.isEmpty()) throw new Error("Improvement fixture must remain offscreen.");
      return image.toPNG().toString("base64");
    });
    await writeFile(testInfo.outputPath("held-manuscript-improvement.png"), Buffer.from(png, "base64"));
    await improve.click();
    await expect.poll(async () => (await inspect()).calls).toEqual([[id, "fixture-writer", "fixture-reviewer"]]);
    await expect(improve).toHaveCount(0);
    await expect(held.getByRole("button", { name: "연구 취소", exact: true })).toBeDisabled();
    await selectView(page, "연결");
    await expect(page.getByRole("button", { name: "계정 추가", exact: true })).toBeDisabled();
    await selectView(page, "새 연구");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
    expect((await inspect()).forbiddenCalls).toEqual([]);
    await electronApp.evaluate(() => (globalThis as typeof globalThis & { __paperFactoryImprovementFixture: ImprovementFixture }).__paperFactoryImprovementFixture.release!());
    await selectView(page, "결과");
    await expect(held.getByRole("button", { name: "연구 취소", exact: true })).toBeEnabled();
    expect((await page.evaluate(() => window.paperFactory.researchSnapshot())).busy).toBe(true);
    await selectView(page, "연결");
    await expect(page.getByRole("button", { name: "계정 추가", exact: true })).toBeDisabled();
    await electronApp.evaluate(({ BrowserWindow }, id) => {
      const gate = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      gate.research = { ...gate.research, busy: false, jobs: gate.research.jobs.map(job => job.id === id
        ? { ...job, pipeline: "paused", phase: "idle" } : job) };
      BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", gate.research);
    }, id);
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).busy).toBe(false);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("structured manuscript repairs and follow-up lineage preserve prior results and busy controls", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const connection: AppSnapshot = { version: "fixture", session: { connected: true, sharing: true, profileId: "fixture-a" },
    profiles: [{ id: "fixture-a", label: "Synthetic account", connected: true, sharing: true }],
    models: [{ slug: "fixture-model", displayName: "Synthetic model" }], busy: null, error: null, verification: null };
  const [rootId, childId, nextId, revisionId, infeasibleId] = ["111", "222", "333", "444", "555"]
    .map(value => `research-${value.repeat(4)}`);
  const redesignReview: ManuscriptReview = { ...approvedManuscriptReview, accepted: false,
    issues: ["합성 검토: 실제 적용 범위를 뒷받침할 근거가 부족합니다."],
    contribution: { passed: false, reason: "합성 검토: 현재 관측만으로 제안한 적용 효과를 설명할 수 없습니다." },
    remediation: { strategy: "redesign_study", reason: "합성 보완 판단: 새로운 비교와 관측이 필요한 상황을 표시합니다.",
      actions: [{ criterion: "contribution", action: "합성 보완 행동: 기존 관측을 보존하고 별도의 비교 설계를 마련합니다." }],
      evidence_gaps: ["합성 부족 근거: 실제 입력 다양성을 다룬 별도 비교 관측이 필요합니다."] } };
  const revisionReview: ManuscriptReview = { ...redesignReview,
    remediation: { strategy: "revise_manuscript", reason: "합성 원고 보완: 이미 확보한 부정적 결과를 정확히 설명해야 합니다.",
      actions: [{ criterion: "contribution", action: "합성 원고 행동: 보존된 결과의 제한된 기여를 관련 문헌과 연결합니다." }],
      evidence_gaps: [] } };
  const infeasibleReview: ManuscriptReview = { ...redesignReview,
    remediation: { strategy: "infeasible", reason: "합성 추가 근거 판단: 현재 실행 환경에서 필요한 앱 동작을 관측할 수 없습니다.",
      actions: [{ criterion: "contribution", action: "합성 차단 이유: 지원되는 관측 자료와 연구 요구 사항을 확인해야 합니다." }],
      evidence_gaps: ["합성 차단 근거: 실제 화면 작업의 독립적인 관측 자료가 없습니다."] } };
  const base: Omit<ResearchSnapshot["jobs"][number], "id" | "source" | keyof ReturnType<typeof researchFixture>> = {
    goal: "보완 판단과 연구 연결만 검증하는 합성 UI 연구입니다.", model: "fixture-model", reviewerModel: "fixture-model",
    phase: "manuscript-review", pipeline: "paused", stage: "analyzed", status: "blocked", code: "MANUSCRIPT_REJECTED",
    message: null, updatedAt: "2026-01-01T00:00:00.000Z", artifacts: [], supportingDocuments: [],
    studyReview: approvedStudyReview, manuscriptReview: redesignReview, resumeKind: null,
  };
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 연구 보완 fixture" }, busy: true,
    cleanupResearchIds: [], error: null, jobs: [
      { ...base, ...researchFixture(rootId), id: rootId, source: "https://github.com/fixture-owner/original-study", followupResearchId: childId },
      { ...base, ...researchFixture(childId), id: childId, source: "https://github.com/fixture-owner/first-followup",
        parentResearchId: rootId, rootResearchId: rootId, redesignAttempt: 1, followupResearchId: nextId },
      { ...base, ...researchFixture(nextId), id: nextId, source: "https://github.com/fixture-owner/next-followup",
        parentResearchId: childId, rootResearchId: rootId, redesignAttempt: 2, pipeline: "running", phase: "redesign" },
      { ...base, ...researchFixture(revisionId), id: revisionId, source: "https://github.com/fixture-owner/prose-repair", manuscriptReview: revisionReview },
      { ...base, ...researchFixture(infeasibleId), id: infeasibleId, source: "https://github.com/fixture-owner/missing-evidence", manuscriptReview: infeasibleReview },
    ] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await selectView(page, "결과");
    const original = page.getByRole("article", { name: "original-study", exact: true });
    await expect(original).toContainText("연구 설계 보완: 0/2회");
    await expect(original).toContainText("후속 연구에서 설계를 보완하며 이전 실험 결과는 변경하지 않습니다.");
    await expect(original.getByRole("button")).toHaveCount(0);
    const repair = original.getByRole("region", { name: "원고 보완 방향", exact: true });
    await expect(repair).toContainText("보완 방향 · 새 연구 설계");
    await expect(repair.getByText(redesignReview.remediation!.reason, { exact: true })).toBeVisible();
    await expect(repair.getByText(redesignReview.remediation!.actions[0].action, { exact: true })).toBeVisible();
    await expect(repair.getByText(redesignReview.remediation!.evidence_gaps[0], { exact: true })).toBeVisible();
    await expect(original.getByRole("link", { name: "후속 연구 보기", exact: true })).toHaveAttribute("href", `#${childId}`);
    await original.getByRole("link", { name: "후속 연구 보기", exact: true }).click();
    expect(new URL(page.url()).hash).toBe(`#${childId}`);
    expect(await page.evaluate(() => document.activeElement?.id)).toBe(childId);
    const child = page.getByRole("article", { name: "first-followup", exact: true });
    await expect(child).toContainText("연구 설계 보완: 1/2회");
    await expect(child.getByRole("link", { name: "이전 연구 보기", exact: true })).toHaveAttribute("href", `#${rootId}`);
    await expect(child.getByRole("link", { name: "후속 연구 보기", exact: true })).toHaveAttribute("href", `#${nextId}`);
    const next = page.getByRole("article", { name: "next-followup", exact: true });
    await expect(next).toContainText("연구 설계 보완: 2/2회");
    await expect(next).toContainText("연구 설계 보완 (redesign)");
    await expect(next.getByRole("link", { name: "최초 연구 보기", exact: true })).toHaveAttribute("href", `#${rootId}`);
    await expect(next.getByRole("button", { name: "연구 취소", exact: true })).toBeEnabled();
    const revision = page.getByRole("article", { name: "prose-repair", exact: true }).getByRole("region", { name: "원고 보완 방향", exact: true });
    await expect(revision).toContainText("보완 방향 · 원고 보완");
    await expect(revision.getByText("부족한 근거", { exact: true })).toHaveCount(0);
    const infeasible = page.getByRole("article", { name: "missing-evidence", exact: true }).getByRole("region", { name: "원고 보완 방향", exact: true });
    await expect(infeasible).toContainText("보완 방향 · 추가 근거 필요");
    await expect(infeasible.getByText(infeasibleReview.remediation!.evidence_gaps[0], { exact: true })).toBeVisible();
    await original.evaluate(element => element.scrollIntoView({ block: "start" }));
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    const captureWindow = await electronApp.browserWindow(page);
    const png = await captureWindow.evaluate(async window => {
      const image = await window.webContents.capturePage(undefined, { stayHidden: true });
      if (window.isVisible() || image.isEmpty()) throw new Error("Follow-up fixture must remain offscreen.");
      return image.toPNG().toString("base64");
    });
    await writeFile(testInfo.outputPath("structured-repair-followup.png"), Buffer.from(png, "base64"));
    await selectView(page, "새 연구");
    await expect(page.getByRole("button", { name: "연구 시작", exact: true })).toBeDisabled();
    await selectView(page, "연결");
    await expect(page.getByRole("button", { name: "계정 추가", exact: true })).toBeDisabled();
    expect(await electronApp.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls)).toEqual([]);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("research and manuscript quality rejections show reasons without presenting completion or restart actions", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const connection: AppSnapshot = { version: "fixture", session: { connected: true, sharing: true, profileId: "fixture-a" },
    profiles: [{ id: "fixture-a", label: "Synthetic account", connected: true, sharing: true }],
    models: [{ slug: "fixture-model", displayName: "Synthetic model" }], busy: null, error: null, verification: null };
  const passed = { passed: true, reason: "합성 평가에서 충족한 항목입니다." };
  const studyReview = { accepted: false, issues: ["실제 사용에서 의미 있는 비교 정책이 필요합니다."],
    question: passed, contribution: { passed: false, reason: "함수의 정해진 동작 확인만으로 새로운 연구 기여가 되지 않습니다." },
    literature: passed, comparison: { passed: false, reason: "비교 구현이 필요한 기능을 일부러 생략했습니다." },
    sampling: passed, feasibility: passed, selected_sources: [] };
  const manuscriptReview = { accepted: false, issues: ["함수 검사 결과의 주장 범위를 줄여야 합니다."], checks: [],
    contribution: passed, literature: passed,
    interpretation: { passed: false, reason: "합성 입력 결과를 실제 앱 전체의 효과로 확대했습니다." }, presentation: passed };
  const base: Omit<ResearchSnapshot["jobs"][number], "id" | "source" | keyof ReturnType<typeof researchFixture>> = {
    goal: "검토 반려 이유 표시만 확인하는 합성 연구입니다.", model: "fixture-model", reviewerModel: "fixture-model",
    phase: "study-review", pipeline: "failed", stage: "proposed", status: "blocked", code: "STUDY_REJECTED",
    message: "합성 연구 설계 보류", updatedAt: "2026-01-01T00:00:00.000Z", artifacts: [], supportingDocuments: [],
    studyReview, manuscriptReview: null, resumeKind: null,
  };
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 품질 검토 fixture" }, busy: false,
    cleanupResearchIds: [], error: null, jobs: [
      { ...base, ...researchFixture("research-111111111111"), id: "research-111111111111", source: "https://github.com/fixture-owner/study-rejected",
        // Even an inconsistent resume hint must not offer a restart of a final blocked proposal.
        resumeKind: "preparation" },
      { ...base, ...researchFixture("research-222222222222"), id: "research-222222222222", source: "https://github.com/fixture-owner/manuscript-rejected",
        phase: "manuscript-review", stage: "manuscript", code: "MANUSCRIPT_REJECTED", message: "합성 원고 보류",
        studyReview: { ...studyReview, accepted: true, issues: [], contribution: passed, comparison: passed }, manuscriptReview },
      { ...base, ...researchFixture("research-333333333333"), id: "research-333333333333", source: "https://github.com/fixture-owner/retained-draft",
        phase: "idle", pipeline: "completed", stage: "exported", status: "completed", code: null, message: null,
        studyReview: null, artifacts: [{ id: "export-pdf", sha256: "a".repeat(64), size: 18 }] },
      { ...base, ...researchFixture("research-444444444444"), id: "research-444444444444", source: "https://github.com/fixture-owner/proposal-being-revised",
        pipeline: "running", message: "합성 제안 보완 중" },
      { ...base, ...researchFixture("research-555555555555"), id: "research-555555555555", source: "https://github.com/fixture-owner/retained-study-only",
        phase: "idle", pipeline: "completed", stage: "exported", status: "completed", code: null, message: null,
        studyReview: approvedStudyReview, manuscriptReview: null,
        artifacts: [{ id: "export-pdf", sha256: "a".repeat(64), size: 18 }] },
      { ...base, ...researchFixture("research-666666666666"), id: "research-666666666666", source: "https://github.com/fixture-owner/infeasible-study",
        phase: "plan", code: "STUDY_INFEASIBLE", message: "합성 연구 실행 가능성 보류", resumeKind: "preparation" },
    ] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await selectView(page, "결과");
    const rejectedStudy = page.getByRole("article", { name: "study-rejected", exact: true });
    await expect(rejectedStudy.getByText("연구 보류", { exact: true })).toBeVisible();
    await expect(rejectedStudy).toContainText("연구 적합성 검토 (study-review)");
    await expect(rejectedStudy.getByText("새로운 기여 · 미충족", { exact: true })).toBeVisible();
    await expect(rejectedStudy.getByText(studyReview.contribution.reason, { exact: true })).toBeVisible();
    await expect(rejectedStudy.getByText(studyReview.comparison.reason, { exact: true })).toBeVisible();
    await expect(rejectedStudy.getByRole("button")).toHaveCount(0);
    const infeasibleStudy = page.getByRole("article", { name: "infeasible-study", exact: true });
    await expect(infeasibleStudy.getByText("연구 보류", { exact: true })).toBeVisible();
    await expect(infeasibleStudy.getByText("실패", { exact: true })).toHaveCount(0);
    await expect(infeasibleStudy.getByText("현재 실행 환경과 확보한 근거로 연구 기준을 충족하는 설계를 마련하지 못해", { exact: false })).toBeVisible();
    await expect(infeasibleStudy.getByRole("button")).toHaveCount(0);
    const rejectedManuscript = page.getByRole("article", { name: "manuscript-rejected", exact: true });
    await expect(rejectedManuscript.getByText("원고 보류", { exact: true })).toBeVisible();
    await expect(rejectedManuscript.getByText(manuscriptReview.interpretation.reason, { exact: true })).toBeVisible();
    await expect(rejectedManuscript.getByRole("button")).toHaveCount(0);
    const retainedDraft = page.getByRole("article", { name: "retained-draft", exact: true });
    await expect(retainedDraft.getByText("원고 생성 완료", { exact: true })).toBeVisible();
    await expect(retainedDraft.getByText("이 결과에는 현재 기준의 연구 적합성 검토 기록이 없습니다.", { exact: true })).toBeVisible();
    await expect(retainedDraft.getByText("이 결과에는 현재 기준의 원고 품질 검토 기록이 없습니다.", { exact: true })).toBeVisible();
    await expect(retainedDraft).toContainText("학술지 심사나 채택을 의미하지 않습니다.");
    await expect(retainedDraft.getByText("연구 적합성 검토 · 통과", { exact: true })).toHaveCount(0);
    await expect(retainedDraft.getByRole("button", { name: "원고 수정", exact: true })).toHaveCount(0);
    await expect(retainedDraft.getByText("원고 수정은 보존된 실험 결과로 새 원고와 리뷰를 작성합니다.", { exact: false })).toHaveCount(0);
    const retainedStudyOnly = page.getByRole("article", { name: "retained-study-only", exact: true });
    await expect(retainedStudyOnly.getByText("이 결과에는 현재 기준의 원고 품질 검토 기록이 없습니다.", { exact: true })).toBeVisible();
    await expect(retainedStudyOnly.getByRole("button", { name: "원고 수정", exact: true })).toHaveCount(0);
    const proposalBeingRevised = page.getByRole("article", { name: "proposal-being-revised", exact: true });
    await expect(proposalBeingRevised.getByText("진행 중", { exact: true })).toBeVisible();
    await expect(proposalBeingRevised.getByText("연구 보류", { exact: true })).toHaveCount(0);
    const captureWindow = await electronApp.browserWindow(page);
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    for (const [article, name] of [["study-rejected", "quality-review-rejections"],
      ["manuscript-rejected", "quality-manuscript-rejection"], ["retained-draft", "quality-retained-draft"]] as const) {
      await page.getByRole("article", { name: article, exact: true }).evaluate(element => element.scrollIntoView({ block: "start" }));
      const png = await captureWindow.evaluate(async (window) => {
        const image = await window.webContents.capturePage(undefined, { stayHidden: true });
        if (window.isVisible() || image.isEmpty()) throw new Error("Offscreen quality fixture capture failed.");
        return image.toPNG().toString("base64");
      });
      await writeFile(testInfo.outputPath(`${name}.png`), Buffer.from(png, "base64"));
    }
    expect(await electronApp.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls)).toEqual([]);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});
