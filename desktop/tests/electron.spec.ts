import { _electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";
import { access, mkdir, mkdtemp, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { basename, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import type { AppSnapshot, PaperFactoryApi } from "../src/shared/contracts";
import type { CreateResearchInput, ManuscriptReview, RepositoryPaperDraft, RepositoryPaperReview, RepositoryPortfolioProgress, ResearchSnapshot, StudyReview } from "../src/shared/research";
import { NEW_RESEARCH_MODE, inspectRepositoryArticle } from "../src/shared/publication";
import { PUBLICATION_VENUES, type PublicationTarget } from '../src/shared/venues';
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
  return { parentResearchId: null, rootResearchId: id, redesignAttempt: 0, followupResearchId: null, improvementAvailable: false,
    preparationRedesignReview: null, proposalAttempt: 0, studyLiteratureAttempt: 0, redesignQuestionEvidenceCollections: 0,
    redesignQuestionSearchRepairPlans: 0, redesignQuestionSearchRepairCollections: 0,
    redesignQuestionReframingPlans: 0, redesignQuestionReframingComparisons: 0, redesignQuestionReframingStatus: null,
    codeAttempt: 0,
    preparationRepairAttempt: 0, preparationRepair: null, preparationOriginal: null,
    executionAttempt: 0, draftAttempt: 0, manuscriptAvailable: false,
    submissionContract: null, submissionReadiness: null, manuscriptClaim: null, researchLedger: null, plannedClaim: null,
    submissionRequirements: null, submissionConfirmation: null, authorMetadata: null };
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
const appEntry = ${JSON.stringify(new URL("../dist/app.js", import.meta.url).href)};
registerHooks({ load(url, context, nextLoad) {
  const loaded = nextLoad(url, context);
  if (url !== appEntry) return loaded;
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
      "addResearchEvidence", "admitRepositoryPortfolioEvidence", "cancel", "cancelResearch", "checkRuntime", "correctRepositoryPortfolioLayout", "createResearch", "disconnect", "exportRepositoryPortfolioAuthor", "improveResearch", "listPublicRepositories", "onResearchSnapshot", "onSnapshot",
      "openArtifact", "openUsage", "reformatRepositoryPortfolioDraft", "reformatResearchDraft", "refreshModels", "requestRepositoryPortfolio", "requestRepositoryRevision", "researchSnapshot", "resumeResearch", "saveArtifact", "selectProfile", "setResearchAuthorMetadata", "showArtifactFolder", "signIn", "snapshot", "verify",
    ]);
    expect(rendererSurface.csp).toContain("script-src 'self'");
    expect(rendererSurface.csp).toContain("object-src 'none'");
    expect(rendererSurface.csp).not.toContain("script-src 'self' 'unsafe-inline'");
    for (const request of [{ id: "invalid", model: "fixture" }, { id: "research-abcdef123456", model: "" }]) {
      const denied = await page.evaluate(async ({ id, model }) => {
        try { await window.paperFactory.resumeResearch(id, model, "fixture-reviewer"); return false; }
        catch { return true; }
      }, request);
      expect(denied).toBe(true);
      expect(await page.evaluate(async ({ id, model }) => {
        try { await window.paperFactory.improveResearch(id, model, "fixture-reviewer"); return false; }
        catch { return true; }
      }, request)).toBe(true);
    }
    for (const request of [{ id: "invalid", artifactId: "export-pdf" }, { id: "research-abcdef123456", artifactId: "unsupported" }]) {
      expect(await page.evaluate(async ({ id, artifactId }) => {
        try { await window.paperFactory.saveArtifact(id, artifactId); return false; }
        catch { return true; }
      }, request)).toBe(true);
    }
    for (const request of [{ id: 'invalid', venueId: 'ieee-software' }, { id: 'research-abcdef123456', venueId: '../ieee-software' }]) {
      expect(await page.evaluate(async ({ id, venueId }) => {
        try { await window.paperFactory.exportRepositoryPortfolioAuthor(id, venueId); return false; }
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
    runtime: { state: "ready", message: "합성 fixture 실행 환경입니다. 실제 런타임 검증이 아닙니다.", repositoryAnalysisReady: true },
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
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state, { timeout: 60_000 })
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

    // Historical papers retain their exports without offering new generation actions.
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
    await expect(page.getByText("과거 실험 연구 · 읽기 전용.", { exact: false })).toBeVisible();
    await expect(page.getByText("재개·보완·원고 수정에 사용할 모델", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "원고 수정", exact: true })).toHaveCount(0);
    expect((await inspectFixture()).revisions).toEqual([]);
    await expect(page.getByRole("button", { name: "연구 준비 재개", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "원고 작성 재개", exact: true })).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath("completed-paper-read-only.png"), animations: "disabled", fullPage: true });
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
from paper_factory.autonomous.models import FrozenArtifact, ResearchPlan
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
plan = ResearchPlan.model_validate({
    "feasible": True, "reason": "Synthetic native restore fixture only; no scientific execution or approval.",
    "title": "Synthetic native restore and save lease contract fixture",
    "question": "Does an isolated native restore preserve its frozen synthetic planned hypothesis?",
    "research_gap": "Synthetic product test only; no actual scientific gap is asserted.",
    "expected_contribution": "Synthetic restoration checks establish no academic contribution.",
    "comparison_rationale": "An explicit synthetic comparator exercises protocol validation only.",
    "sampling_rationale": "Fixed synthetic annotations do not constitute representative sampling.",
    "runtime": "quickjs", "source_files": ["transform.js"], "production_entrypoint": "transform.js:transform",
    "dependencies": [], "conditions": ["production", "ablation"],
    "metrics": [{"name": "error", "unit": "events", "description": "Synthetic contract violations for restoration tests only."}],
    "comparator": "An explicit guard removal ablation preserves other synthetic rules.",
    "independent_oracle": "Synthetic fixture annotations define expected values independently.",
    "sampling_unit": "An independently seeded synthetic input with fixture annotations.",
    "units_per_seed": 3, "seeds": [11, 37], "parameters": {"fixture_size": 12},
    "procedure": ["Declare seeded synthetic annotations.", "Describe production and explicit comparator without execution.",
        "Preserve frozen metadata for independent restoration inspection."],
    "analysis_method": "Synthetic descriptive comparison; no observations are supplied.",
    "limitations": ["Synthetic fixture does not establish any scholarly result.", "No measurements or scientific execution are supplied."],
    "literature_queries": ["synthetic product restoration contract"],
    "research_claim": {"mode": "finite_enumeration", "claim": "Frozen synthetic planned hypothesis for native reopen; not an observed result.",
        "scope": "Only the isolated native restoration fixture; no real repository or publication claim.",
        "importance": "Synthetic product restoration validation only; no scholarly importance is asserted.",
        "validation_plan": "Retained synthetic metadata validates restoration without running a scientific experiment."},
})
plan_path = ws.path("research/plan-fixture.json")
write_json(plan_path, plan.model_dump())
record.artifacts["plan"] = FrozenArtifact(path=plan_path.relative_to(ws.root).as_posix(), sha256=digest_file(plan_path), size=plan_path.stat().st_size)
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
    const nativePlan = JSON.parse(await readFile(join(engineHome, "workflows", id, "research", "plan-fixture.json"), "utf8"));
    const plannedClaim = { claim: nativePlan.research_claim.claim, scope: nativePlan.research_claim.scope, mode: nativePlan.research_claim.mode };
    const planBytes = await readFile(join(engineHome, "workflows", id, "research", "plan-fixture.json"));
    expect(research.jobs[0]).toMatchObject({ id, pipeline: "paused", code: "SUBMISSION_PENDING", stage: "exported", status: "completed",
      resumeKind: null, plannedClaim, manuscriptClaim: null, proposalAttempt: 0, studyLiteratureAttempt: 0, executionAttempt: 0, draftAttempt: 0 });
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
        () => window.paperFactory.resumeResearch(id, "fixture", "fixture"),
        () => window.paperFactory.improveResearch(id, "fixture", "fixture"),
        () => window.paperFactory.saveArtifact(id, "export-pdf"),
      ];
      const failures: string[] = [];
      for (const operation of operations) {
        try { await operation(); failures.push("unexpected-success"); }
        catch (error) { failures.push(String(error)); }
      }
      return failures;
    }, id);
    expect(rejected).toHaveLength(9);
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
    // A genuine second startup reads the compact native list, without fetching full status or running a model.
    electronApp = await launch(dataDir); exited = false;
    const reopenedPage = await electronApp.firstWindow();
    await expect.poll(async () => (await reopenedPage.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state, { timeout: 60_000 }).toBe("ready");
    await expect.poll(async () => (await reopenedPage.evaluate(() => window.paperFactory.researchSnapshot())).busy, { timeout: 60_000 }).toBe(false);
    const reopened = await reopenedPage.evaluate(() => window.paperFactory.researchSnapshot());
    expect(reopened.jobs).toHaveLength(1);
    expect(reopened.jobs[0]).toMatchObject({ id, plannedClaim, manuscriptClaim: null, pipeline: "paused", code: "SUBMISSION_PENDING",
      proposalAttempt: 0, studyLiteratureAttempt: 0, codeAttempt: 0, executionAttempt: 0, draftAttempt: 0, redesignAttempt: 0 });
    expect(reopened.jobs[0].artifacts).toEqual(research.jobs[0].artifacts);
    expect(reopened.jobs[0].source).toBe(research.jobs[0].source);
    const reopenedConnection = await reopenedPage.evaluate(() => window.paperFactory.snapshot());
    expect(reopenedConnection.session).toEqual({ connected: false, sharing: false });
    expect(reopenedConnection.profiles).toEqual([]); expect(reopenedConnection.models).toEqual([]);
    await selectView(reopenedPage, "결과");
    const hypothesis = reopenedPage.getByRole("region", { name: "계획 가설과 실제 관측 결론", exact: true });
    await expect(hypothesis).toContainText(plannedClaim.claim);
    await expect(hypothesis).toContainText(plannedClaim.scope);
    await expect(hypothesis).toContainText("아직 실제 관측 결론이 동결되지 않았습니다. 계획 가설은 관측 결과가 아닙니다.");
    await hypothesis.scrollIntoViewIfNeeded();
    await reopenedPage.evaluate(() => new Promise<void>(resolveFrame => requestAnimationFrame(() => requestAnimationFrame(() => resolveFrame()))));
    await reopenedPage.screenshot({ path: testInfo.outputPath("native-lightweight-reopen-planned-hypothesis.png"), animations: "disabled", fullPage: true });
    expect(await readFile(join(engineHome, "workflows", id, "research", "plan-fixture.json"))).toEqual(planBytes);
    expect((await readFile(journal, "utf8")).trim().split("\n").map(line => JSON.parse(line).event)).toEqual(["launch", "launch"]);
    await electronApp.close(); exited = true;
    const { stdout: reopenedRecord } = await promisify(execFile)(python, ["-I", "-B", "-c", readRecord, engineHome],
      { cwd: fixtureRoot, env: seedEnv, timeout: 30_000, windowsHide: true });
    expect(JSON.parse(reopenedRecord)).toEqual(JSON.parse(originalRecord));
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
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 파일 저장 fixture", repositoryAnalysisReady: true }, busy: false,
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
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state, { timeout: 60_000 }).not.toBe("checking");
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
    await expect(page.getByRole("button", { name: "원고 수정", exact: true })).toHaveCount(0);
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
      "research:create", "research:resume", "research:revise-writing", "research:improve", "research:add-evidence",
      "research:submission-requirements", "research:submission-confirm", "research:author-metadata", "research:repository-revision", "research:repository-portfolio"]) ipcMain.removeHandler(channel);
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
      "research:create", "research:resume", "research:revise-writing", "research:improve", "research:add-evidence",
      "research:submission-requirements", "research:submission-confirm", "research:author-metadata", "research:repository-revision", "research:repository-portfolio"]) {
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
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state, { timeout: 60_000 }).not.toBe("checking");
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
    await expect(page.getByRole("button", { name: "연구 준비 재개", exact: true })).toHaveCount(0);
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
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 실행 환경", repositoryAnalysisReady: true }, busy: false,
    cleanupResearchIds: [], jobs: [], error: null };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state, { timeout: 60_000 }).not.toBe("checking");
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

test("new research supports two IEEE venues while historical studies retain their state and exports without generation actions", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const connection: AppSnapshot = { version: "fixture", session: { connected: true, sharing: true, profileId: "fixture-a" },
    profiles: [{ id: "fixture-a", label: "Synthetic account", connected: true, sharing: true }],
    models: [{ slug: "fixture-model", displayName: "Synthetic model" }], busy: null, error: null, verification: null };
  const heldId = "research-abcdef111111";
  const exportedId = "research-abcdef222222";
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 분석 환경", repositoryAnalysisReady: true },
    busy: false, cleanupResearchIds: [], error: null, jobs: [
      { ...researchFixture(heldId), id: heldId, source: "https://github.com/fixture-owner/historical-held",
        researchMode: "empirical", goal: "과거 설계의 상태와 심사를 유지합니다.", model: "fixture-model", reviewerModel: "fixture-model",
        phase: "study-review", pipeline: "failed", stage: "proposed", status: "blocked", resumeKind: "preparation",
        code: "STUDY_REJECTED", message: "기존 설계 보류 기록입니다.", updatedAt: "2026-01-01T00:00:00.000Z",
        proposalAttempt: 3, studyLiteratureAttempt: 2, improvementAvailable: true,
        artifacts: [{ id: "study-review", sha256: "b".repeat(64), size: 120 }], supportingDocuments: [],
        studyReview: { ...approvedStudyReview, accepted: false, issues: ["보존된 설계 비교 근거가 부족합니다."] }, manuscriptReview: null },
      { ...researchFixture(exportedId), id: exportedId, source: "https://github.com/fixture-owner/historical-export",
        researchMode: "empirical", goal: "과거 원고와 실행 횟수를 유지합니다.", model: "fixture-model", reviewerModel: "fixture-model",
        phase: "idle", pipeline: "completed", stage: "exported", status: "completed", resumeKind: "authoring",
        code: null, message: "기존 원고와 실험 기록입니다.", updatedAt: "2026-01-02T00:00:00.000Z",
        proposalAttempt: 2, studyLiteratureAttempt: 1, codeAttempt: 2, executionAttempt: 1, draftAttempt: 2,
        manuscriptAvailable: true, improvementAvailable: true,
        artifacts: ["export-pdf", "export-md", "analysis"].map(id => ({ id, sha256: "a".repeat(64), size: 180 })),
        supportingDocuments: [{ id: "document-abcdef123456", name: "retained-evidence.pdf", sha256: "c".repeat(64), size: 420 }],
        studyReview: approvedStudyReview, manuscriptReview: approvedManuscriptReview },
    ] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state,
      { timeout: 60_000 }).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await electronApp.evaluate(({ ipcMain }) => {
      const fixture = (globalThis as typeof globalThis & {
        __paperFactoryGateFixture: GateFixture & { created: CreateResearchInput[] };
      }).__paperFactoryGateFixture;
      fixture.created = [];
      ipcMain.removeHandler("research:create");
      ipcMain.handle("research:create", (_event, input: CreateResearchInput) => {
        fixture.created.push(input); return fixture.research;
      });
    });
    await selectView(page, "새 연구");
    await expect(page.locator("#research-mode")).toHaveCount(0);
    await page.getByText('지원하는 두 IEEE 매체와 공식 안내', { exact: true }).click();
    for (const venue of PUBLICATION_VENUES) await expect(page.locator('#research-panel').getByRole('link', { name: `${venue.name} 공식 작성 안내`, exact: true }))
      .toHaveAttribute('href', venue.guidelines_url);
    const source = "https://github.com/fixture-owner/current-repository";
    const goal = "실무 설계 판단과 한계에 대한 IEEE Software 원고를 작성합니다.";
    await page.getByLabel("공개 GitHub 저장소 또는 계정 URL", { exact: true }).fill(source);
    await page.getByLabel("연구 목표", { exact: true }).fill(goal);
    await page.getByRole("button", { name: "연구 시작", exact: true }).click();
    await expect.poll(() => electronApp!.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture & { created: CreateResearchInput[] } })
        .__paperFactoryGateFixture.created)).toEqual([{ source, goal, model: "fixture-model", reviewerModel: "fixture-model",
          researchMode: NEW_RESEARCH_MODE }]);
    await selectView(page, "결과");
    for (const name of ["historical-held", "historical-export"]) {
      const article = page.getByRole("article", { name, exact: true });
      await expect(article.getByText("과거 실험 연구 · 읽기 전용.", { exact: false })).toBeVisible();
      for (const action of ["연구 준비 재개", "원고 작성 재개", "원고 검토 재개", "연구 설계 보완", "원고 보완 이어가기",
        "원고 수정", "첨부 근거 추가", "저자 정보 저장", "출력 다시 생성"]) {
        await expect(article.getByRole("button", { name: action, exact: true })).toHaveCount(0);
      }
    }
    const held = page.getByRole("article", { name: "historical-held", exact: true });
    await expect(held).toContainText("proposed · blocked");
    await expect(held).toContainText("보존된 설계 비교 근거가 부족합니다.");
    await expect(held.getByRole("region", { name: "연구 진행 횟수", exact: true })).toContainText("정식 설계 제출: 3/3회");
    const exported = page.getByRole("article", { name: "historical-export", exact: true });
    await expect(exported).toContainText("exported · completed");
    await expect(exported.getByRole("region", { name: "연구 진행 횟수", exact: true })).toContainText("과학실험 실행: 1/1회");
    await expect(exported.getByRole("region", { name: "연구 진행 횟수", exact: true })).toContainText("원고 작성: 2회");
    for (const action of ["PDF 열기", "PDF 저장", "Markdown 열기", "Markdown 저장", "결과 폴더 열기"]) {
      await expect(exported.getByRole("button", { name: action, exact: true })).toBeEnabled();
    }
    await exported.getByText("첨부 근거 1개", { exact: true }).click();
    await expect(exported).toContainText("retained-evidence.pdf · 420 바이트");
    expect((await page.evaluate(() => window.paperFactory.researchSnapshot())).jobs).toEqual(research.jobs);
    expect(await electronApp.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls)).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("ieee-software-historical-read-only.png"), animations: "disabled", fullPage: true });
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("two IEEE submissions show independent holds and real output identities while resume preserves the common study", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const connection: AppSnapshot = { version: 'fixture', session: { connected: true, sharing: true },
    profiles: [], models: [{ slug: 'fixture-model', displayName: 'Synthetic model' }], busy: null, error: null, verification: null };
  const id = 'research-abcdef444444';
  const draft: RepositoryPaperDraft = { title: 'Retained common study fixture', sections: [
    { heading: 'Abstract', text: 'Synthetic UI data only, with no executed study or asserted publication quality.' },
    { heading: 'Method', text: 'Retained source fixtures do not claim runtime execution.' },
  ], source_evidence: [], literature_evidence: [], document_evidence: [], revision: null };
  const assessment = { comparison: syntheticQualityCriterion, contribution: syntheticQualityCriterion, issues: [], next_actions: [],
    literature_queries: [], pdf_candidates: [], revision_outline: [] };
  const review: RepositoryPaperReview = { criteria: { supported_findings: syntheticQualityCriterion, contribution: syntheticQualityCriterion,
    literature: syntheticQualityCriterion, method: syntheticQualityCriterion, presentation: syntheticQualityCriterion,
    empirical_claims_absent: syntheticQualityCriterion, venue_fit: syntheticQualityCriterion }, issues: [], next_actions: [], content_assessment: assessment };
  const analysis = { method: 'Retained synthetic source analysis.', codebook: [], units: [], findings: [], counterexamples: [],
    source_evidence: [], literature_evidence: [], document_evidence: [], limitations: ['UI fixture, not actual scientific evidence.'] };
  const portfolio: RepositoryPortfolioProgress = { artifact_id: 'repository-portfolio-start', sha256: 'a'.repeat(64), bindings: {},
    targets: PUBLICATION_VENUES.map(venue => ({ venue_id: venue.id, article_category: venue.article_categories[0] })),
    analysis, analysis_sha256: 'a'.repeat(64), analysis_binding: null, analysis_outcome: null, literature: null, literature_sha256: null, literature_collections: [],
    analysis_revision_required: false, analysis_revision_available: false, analysis_revision: null,
          literature_followup_available: false, documentation_followup_available: false, literature_budget: { used: 2, limit: 3 },
          supplementary_evidence: null, supplementary_evidence_budget: { used: 0, limit: 1 }, supplementary_evidence_available: false,
    pdf_budget: { base_used: 2, additional_limit: 2, additional_used: 0, total_used: 2, base_reservations_sha256: 'b'.repeat(64) },
    guidance: { artifact_id: 'synthetic-guidance', sha256: 'a'.repeat(64), scope: 'Synthetic completed UI guidance fixture.', sources: [] },
    all_content_ready: false, completed: 2, total: PUBLICATION_VENUES.length,
    venues: PUBLICATION_VENUES.map((venue, index) => {
      const prefix = `repository-portfolio-${venue.id}`;
      const held = { passed: false, reason: '기여를 뒷받침할 직접 비교 범위가 부족합니다.' };
      const heldReview: RepositoryPaperReview = { ...review, criteria: { ...review.criteria, contribution: held },
        issues: ['이 학술지에 필요한 비교 근거를 추가해야 합니다.'], next_actions: [],
        content_assessment: { ...assessment, contribution: held, next_actions: [{ action: 'revise_source_analysis',
          target: '직접 비교 범위', required_change: '동일 기준으로 비교한 추가 소스 관측을 보존하세요.', verification: '추가 관측과 원문 근거를 대조합니다.' }] } };
      return { venue_id: venue.id, article_category: venue.article_categories[0], draft_attempts: index < 3 ? 1 : 0,
        review_attempts: index < 2 ? 1 : 0, admitted_drafts: index < 2 ? 1 : 0,
        draft: index < 2 ? { ...draft, title: `${venue.name} targeted UI fixture` } : null,
        review: index === 0 ? review : index === 1 ? heldReview : null, draft_sha256: index < 2 ? 'b'.repeat(64) : null,
        artifact_ids: { draft: index < 2 ? `${prefix}-draft-1` : null, markdown: index < 2 ? `${prefix}-markdown-1` : null,
          review: index < 2 ? `${prefix}-review-1` : null, pdf: index === 0 ? `${prefix}-pdf-1` : index === 1 ? 'repository-draft-pdf-2' : null,
          docx: index < 2 ? `${prefix}-docx-1` : null },
        status: index === 0 ? 'content_ready' : index === 1 ? 'needs_revision' : index === 2 ? 'writing_interrupted' : 'pending_draft',
        writer_binding: index === 1 ? { research_id: id, portfolio_start_sha256: 'a'.repeat(64), source_digest: 'a'.repeat(64),
          source_commit: 'synthetic-commit', plan_sha256: 'a'.repeat(64), base_analysis_sha256: 'a'.repeat(64), catalog_sha256: 'a'.repeat(64),
          guidance_sha256: 'a'.repeat(64), literature_sha256: null, portfolio_analysis_sha256: 'a'.repeat(64), phase: 'venue-manuscript',
          venue_id: venue.id, article_category: venue.article_categories[0], attempt: 2, prior_draft_sha256: 'b'.repeat(64), draft_sha256: null, markdown_sha256: null } : null,
        reviewer_binding: null, writer_outcome: index === 2 ? 'failed' : null, reviewer_outcome: null,
        repair_attempts: 0, repair_binding: null, repair_outcome: null,
        export_repair_available: false, export_repair_attempts: 0, export_repair_total: 0,
        format_export_available: false, format_export_attempts: 0, format_export: null,
        layout_export_available: false, layout_export_attempts: 0, layout_export: null,
        author_export_attempts: 0, author_export_available: false, author_export_status: 'unavailable', author_export: null,
        revise_available: index === 1, revise_reason: '이 매체에 필요한 추가 근거와 보존된 심사를 확인하세요.',
        export_status: index < 2 ? 'completed' : 'not_started', export: null,
        analysis_current: true, scientific_ready: index === 0, content_ready: index === 0, submission_ready: false };
    }) };
  const target: PublicationTarget = { venue_id: 'ieee-security-privacy', article_category: 'Feature Article', selection_reason: 'Retained synthetic target.',
    candidates: PUBLICATION_VENUES.map(venue => ({ venue_id: venue.id, fit: 'needs_evidence', reason: 'Synthetic fixture.', missing_evidence: [] })) };
  const originalArtifacts = ['draft', 'draft-md', 'review', 'draft-pdf', 'draft-docx'].map(kind => ({
    id: `repository-${kind}-2`, sha256: kind === 'draft' ? 'b'.repeat(64) : 'c'.repeat(64), size: 180 }));
  const research: ResearchSnapshot = { runtime: { state: 'ready', message: 'Synthetic engine only.', repositoryAnalysisReady: true },
    busy: false, cleanupResearchIds: [], error: null, jobs: [{ ...researchFixture(id), id, source: 'https://github.com/fixture-owner/ieee-submissions',
      goal: 'Synthetic UI preservation and venue isolation.', researchMode: NEW_RESEARCH_MODE, model: 'fixture-model', reviewerModel: 'fixture-model',
      phase: 'idle', pipeline: 'paused', stage: 'repository_manuscript', status: 'ready', resumeKind: null, code: null, message: null,
      updatedAt: '2026-01-01T00:00:00.000Z', proposalAttempt: 1, draftAttempt: 2, manuscriptAvailable: true,
      artifacts: [...originalArtifacts, ...portfolio.venues.flatMap(venue => Object.values(venue.artifact_ids)
        .filter((artifactId): artifactId is string => !!artifactId && artifactId !== 'repository-draft-pdf-2')
        .map(artifactId => ({ id: artifactId, sha256: artifactId.includes('-draft-') ? 'b'.repeat(64) : 'c'.repeat(64), size: 180 })))],
      supportingDocuments: [], studyReview: null, manuscriptReview: null,
      repositoryPaper: { portfolio, plan: { publication_target: target, article_type: 'technical_analysis', title: draft.title,
        question: 'Retain common study?', contribution: 'Synthetic UI only.', analysis_method: analysis.method, comparison_dimensions: [],
        source_files: [], source_evidence: [], literature_queries: [], limitations: [] }, literature: null, analysis,
        analysis_attempts: 2, analysis_revision_required: false, draft, review, draft_sha256: 'b'.repeat(64), revision_available: false,
        scientific_ready: true, content_ready: true, content_assessment: assessment, submission_ready: false,
        analysis_provenance: { method: 'Synthetic UI only.', execution_performed: false, human_analysis_verified: false, human_approval_verified: false, model_calls: [] },
        revision_feedback: null, revision_feedback_sha256: null, prior_feedback: null,
        artifact_ids: { draft: 'repository-draft-2', draft_markdown: 'repository-draft-md-2', review: 'repository-review-2', pdf: 'repository-draft-pdf-2', docx: 'repository-draft-docx-2' },
        bindings: {}, next_actions: [] } }] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state, { timeout: 60_000 }).not.toBe('checking');
    await installGateFixture(electronApp, connection, research);
    await electronApp.evaluate(({ ipcMain }) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture & { portfolioCalls: string[]; opened: string[] } }).__paperFactoryGateFixture;
      fixture.portfolioCalls = []; fixture.opened = [];
      ipcMain.removeHandler('research:repository-portfolio');
      ipcMain.handle('research:repository-portfolio', (_event, id: string) => { fixture.portfolioCalls.push(id); return fixture.research; });
      ipcMain.removeHandler('research:open-artifact');
      ipcMain.handle('research:open-artifact', (_event, _id: string, artifactId: string) => { fixture.opened.push(artifactId); });
    });
    await selectView(page, '결과');
    const article = page.getByRole('article', { name: 'ieee-submissions', exact: true });
    const portfolioRegion = article.getByRole('region', { name: 'IEEE 매체별 투고본', exact: true });
    await expect(portfolioRegion).toContainText('기존 2회 · 공통 보강 0/2회 · 합산 2회');
    for (const venue of PUBLICATION_VENUES) await expect(portfolioRegion.getByRole('region', { name: `${venue.name} 투고본`, exact: true })).toBeVisible();
    const ready = portfolioRegion.getByRole('region', { name: `${PUBLICATION_VENUES[0].name} 투고본`, exact: true });
    await expect(ready).toContainText('새 원고 작성 1회 · 보존한 새 원고 1개 · 독립 심사 1회');
    await ready.getByRole('button', { name: `${PUBLICATION_VENUES[0].name} PDF 열기`, exact: true }).click();
    const held = portfolioRegion.getByRole('region', { name: `${PUBLICATION_VENUES[1].name} 투고본`, exact: true });
    await expect(held).toContainText('기여를 뒷받침할 직접 비교 범위가 부족합니다.');
    await expect(held).toContainText('동일 기준으로 비교한 추가 소스 관측을 보존하세요.');
    await expect(held.getByRole('button', { name: `${PUBLICATION_VENUES[1].name} PDF 열기`, exact: true })).toHaveCount(0);
    await portfolioRegion.getByRole('button', { name: 'IEEE 매체별 미완료 투고본 재개', exact: true }).click();
    expect(await electronApp.evaluate(() => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture & { portfolioCalls: string[]; opened: string[] } }).__paperFactoryGateFixture;
      return { calls: fixture.portfolioCalls, opened: fixture.opened, forbidden: fixture.forbiddenCalls };
    })).toEqual({ calls: [id], opened: [portfolio.venues[0].artifact_ids.pdf], forbidden: [] });
    expect((await page.evaluate(() => window.paperFactory.researchSnapshot())).jobs).toEqual(research.jobs);
    await expect(article).toContainText('저장소 코드 실행 0회 · 보존한 매체별 실제 원고 2개');
    await expect(article.getByRole('button', { name: '원고 2 · PDF 열기', exact: true })).toBeEnabled();
    await electronApp.evaluate(({ BrowserWindow }) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      const portfolio = fixture.research.jobs[0].repositoryPaper!.portfolio!;
      for (const venue of portfolio.venues) { venue.writer_binding = null; venue.reviewer_binding = null; }
      const first = portfolio.venues[0];
      first.artifact_ids.docx = null; first.export_status = 'failed';
      first.export = { artifact_id: `repository-portfolio-${first.venue_id}-export-1`, sha256: 'c'.repeat(64),
        errors: [{ format: 'docx', message: '합성 Word 변환 실패 기록입니다.' }] };
      BrowserWindow.getAllWindows()[0]?.webContents.send('research:changed', fixture.research);
    });
    await expect(portfolioRegion.getByRole('button', { name: 'IEEE 매체별 미완료 투고본 재개', exact: true })).toBeDisabled();
    await expect(portfolioRegion).toContainText('자동으로 진행할 다음 작업이 없습니다.');
    await expect(ready.getByRole('region', { name: `${PUBLICATION_VENUES[0].name} 출력 변환 진단`, exact: true }))
      .toContainText('합성 Word 변환 실패 기록입니다.');
    await electronApp.evaluate(({ BrowserWindow }) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      const first = fixture.research.jobs[0].repositoryPaper!.portfolio!.venues[0];
      first.export_repair_available = true;
      BrowserWindow.getAllWindows()[0]?.webContents.send('research:changed', fixture.research);
    });
    await expect(portfolioRegion.getByRole('button', { name: 'IEEE 매체별 미완료 투고본 재개', exact: true })).toBeEnabled();
    await expect(ready).toContainText('현재 원고 출력 복구 0/1회');
    await expect(ready.getByRole('region', { name: `${PUBLICATION_VENUES[0].name} 출력 변환 진단`, exact: true }))
      .toContainText('네이티브에서 확인한 출력 문제를 1회 복구합니다.');
    await portfolioRegion.getByRole('button', { name: 'IEEE 매체별 미완료 투고본 재개', exact: true }).click();
    expect(await electronApp.evaluate(() => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture & { portfolioCalls: string[] } }).__paperFactoryGateFixture;
      return { calls: fixture.portfolioCalls, forbidden: fixture.forbiddenCalls, draftAttempt: fixture.research.jobs[0].draftAttempt };
    })).toEqual({ calls: [id, id], forbidden: [], draftAttempt: 2 });
    await electronApp.evaluate(({ BrowserWindow }) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      const first = fixture.research.jobs[0].repositoryPaper!.portfolio!.venues[0];
      first.export_repair_available = false; first.export_repair_attempts = 1; first.export_repair_total += 1;
      BrowserWindow.getAllWindows()[0]?.webContents.send('research:changed', fixture.research);
    });
    await expect(portfolioRegion.getByRole('button', { name: 'IEEE 매체별 미완료 투고본 재개', exact: true })).toBeDisabled();
    await expect(ready.getByRole('region', { name: `${PUBLICATION_VENUES[0].name} 출력 변환 진단`, exact: true }))
      .toContainText('출력 복구 1회 한도를 사용했습니다.');
    await expect(article.getByRole('button', { name: '원고 2 · PDF 열기', exact: true })).toBeEnabled();
    await electronApp.evaluate(({ BrowserWindow, ipcMain }) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture & { authorCalls?: string[][] } }).__paperFactoryGateFixture;
      fixture.authorCalls = [];
      const job = fixture.research.jobs[0], first = job.repositoryPaper!.portfolio!.venues[0];
      job.authorMetadata = { origin: 'explicit_human_author_metadata', artifact_id: 'author-metadata-aaaaaaaaaaaa', sha256: 'a'.repeat(64),
        bindings: {}, scope: 'Synthetic explicit author fixture; no submission approval.',
        value: { display_name: 'Synthetic Author', email: 'author@example.test', affiliation: 'Synthetic Institute' } };
      first.author_export_attempts = 2; first.author_export_available = true; first.author_export_status = 'not_started';
      ipcMain.removeHandler('research:portfolio-author');
      ipcMain.handle('research:portfolio-author', (_event, researchId: string, venueId: string) => {
        if (researchId !== job.id || venueId !== first.venue_id) throw new Error('Unexpected fixture author output');
        fixture.authorCalls!.push([researchId, venueId]);
        first.author_export_attempts = 3; first.author_export_available = false; first.author_export_status = 'interrupted';
        BrowserWindow.getAllWindows()[0]?.webContents.send('research:changed', fixture.research);
        return fixture.research;
      });
      BrowserWindow.getAllWindows()[0]?.webContents.send('research:changed', fixture.research);
    });
    const authorButton = ready.getByRole('button', { name: `${PUBLICATION_VENUES[0].name} 저자 정보 반영해 출력`, exact: true });
    await expect(authorButton).toBeEnabled();
    await expect(ready).toContainText('현재 저자 정보가 반영된 PDF·Word가 확인되지 않았습니다.');
    await authorButton.click();
    await expect(authorButton).toHaveCount(0);
    await expect(ready).toContainText('현재 원고 저자 정보 출력 3/3회 · 남은 0회');
    await expect(ready).toContainText('저자 출력 중단 기록과 사용 횟수를 보존했습니다.');
    expect(await electronApp.evaluate(() => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture & { authorCalls: string[][] } }).__paperFactoryGateFixture;
      return { calls: fixture.authorCalls, forbidden: fixture.forbiddenCalls, submissionReady: fixture.research.jobs[0].repositoryPaper!.portfolio!.venues[0].submission_ready };
    })).toEqual({ calls: [[id, PUBLICATION_VENUES[0].id]], forbidden: [], submissionReady: false });
    await page.screenshot({ path: testInfo.outputPath('two-ieee-independent-submission-cards.png'), animations: 'disabled', fullPage: true });
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});

test("IEEE editorial blockers prefill feedback without a request and changed authors distinguish current from previous outputs", async ({}, testInfo) => {
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  let electronApp: ElectronApplication | undefined;
  const connection: AppSnapshot = { version: "fixture", session: { connected: true, sharing: true, profileId: "fixture-a" },
    profiles: [{ id: "fixture-a", label: "Synthetic account", connected: true, sharing: true }],
    models: [{ slug: "fixture-model", displayName: "Synthetic model" }], busy: null, error: null, verification: null };
  const id = "research-abcdef333333";
  const digest = (letter: string) => letter.repeat(64);
  const draft: RepositoryPaperDraft = { title: "Synthetic retained source analysis", sections: [
    { heading: "Abstract", text: "A synthetic article for checking retained UI status." },
    { heading: "Method", text: "The fixture describes only source inspection, with no claimed execution." },
  ], source_evidence: [], literature_evidence: [], document_evidence: [], revision: null };
  const target: PublicationTarget = { venue_id: 'ieee-software', article_category: 'Feature Article', selection_reason: '합성 UI에서 형식과 출력 상태만 확인합니다.',
    candidates: PUBLICATION_VENUES.map(venue => ({ venue_id: venue.id, fit: venue.id === 'ieee-software' ? 'suitable' : 'needs_evidence',
      reason: '합성 UI 비교 기록입니다.', missing_evidence: [] })) };
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 분석 환경", repositoryAnalysisReady: true },
    busy: false, cleanupResearchIds: [], error: null, jobs: [{ ...researchFixture(id), id,
      source: "https://github.com/fixture-owner/publication-status", goal: "기존 판정과 출력의 연결만 확인하는 합성 상태입니다.",
      researchMode: NEW_RESEARCH_MODE, model: "fixture-model", reviewerModel: "fixture-model", phase: "idle", pipeline: "paused",
      stage: "repository_manuscript", status: "ready", code: null, message: "보존된 합성 원고입니다.", resumeKind: null,
      updatedAt: "2026-01-01T00:00:00.000Z", proposalAttempt: 1, draftAttempt: 2, manuscriptAvailable: true,
      artifacts: [
        { id: "repository-draft-2", sha256: digest("f"), size: 120 },
        { id: "repository-draft-md-2", sha256: digest("d"), size: 120 },
        { id: "repository-review-2", sha256: digest("e"), size: 120 },
        { id: "repository-draft-md-2-format-1", sha256: digest("d"), size: 120 },
        ...["repository-draft-pdf-2-format-1", "repository-draft-docx-2-format-1", "repository-draft-pdf-1",
          "repository-draft-docx-1", "repository-draft-pdf-2-format-1-conversion", "repository-draft-docx-2-format-1-conversion",
          "repository-draft-format-2-format-1"].map(id => ({ id, sha256: digest("a"), size: 180 })),
      ], supportingDocuments: [], studyReview: null, manuscriptReview: null,
      repositoryPaper: { plan: { publication_target: target, article_type: 'technical_analysis', title: draft.title,
        question: 'Does the UI retain the selected venue?', contribution: 'Synthetic UI only.', analysis_method: 'Synthetic UI inspection.',
        comparison_dimensions: [], source_files: [], source_evidence: [], literature_queries: [], limitations: [] },
        literature: null, draft, draft_sha256: digest("f"), analysis_attempts: 1, analysis_revision_required: false,
        analysis: { method: '합성 UI용 소스 관측 기록이며 실제 연구 결과가 아닙니다.',
          codebook: [{ dimension: 'authority', definition: '합성 호출의 권한 결정 위치를 관측합니다.' }],
          units: [{ id: 'unit-a', label: 'Synthetic bridge', evidence_ids: ['source-a'],
            observations: [{ dimension: 'authority', finding: '합성 관측은 명시한 호출 위치에 한정됩니다.', evidence_ids: ['source-a'] }] }],
          findings: [{ id: 'finding-a', claim: '합성 발견의 근거 연결을 표시합니다.', unit_ids: ['unit-a'], evidence_ids: ['source-a'], limitations: '실제 프로젝트 결과가 아닙니다.' }],
          counterexamples: [{ finding_id: 'finding-a', condition: '합성 가정이 달라지는 경우', evidence_ids: ['source-a'], implication: '실제 보안 효력을 추정하지 않습니다.' }],
          source_evidence: [{ id: 'source-a', path: 'synthetic/main.ts', sha256: digest('a'), quote: 'synthetic source', interpretation: '합성 UI 원문입니다.' }],
          literature_evidence: [], document_evidence: [], limitations: ['실제 연구 결과가 아닙니다.'] },
        review: { criteria: { supported_findings: syntheticQualityCriterion, contribution: syntheticQualityCriterion,
          literature: syntheticQualityCriterion, method: syntheticQualityCriterion, presentation: syntheticQualityCriterion,
          empirical_claims_absent: syntheticQualityCriterion, venue_fit: syntheticQualityCriterion }, issues: [], next_actions: [] },
        revision_available: false, scientific_ready: true, submission_ready: false, content_ready: true,
        content_assessment: { comparison: syntheticQualityCriterion, contribution: syntheticQualityCriterion, issues: [], next_actions: [],
          literature_queries: [], pdf_candidates: [], revision_outline: [] },
        venueFormat: inspectRepositoryArticle(draft, target),
        analysis_provenance: { method: "Synthetic UI fixture", execution_performed: false, human_analysis_verified: false,
          human_approval_verified: false, model_calls: [] }, revision_feedback: null, revision_feedback_sha256: null, prior_feedback: null,
        artifact_ids: { draft: "repository-draft-2", draft_markdown: "repository-draft-md-2", review: "repository-review-2", pdf: "repository-draft-pdf-2-format-1",
          docx: "repository-draft-docx-2-format-1" }, bindings: {}, next_actions: [],
        formatting_receipts: [{ artifact_id: "repository-draft-format-2-format-1", draft_attempt: 2, attempt: 1, status: "completed",
          markdown_sha256: digest("d"), draft_sha256: digest("f"), review_sha256: digest("e"),
          input_artifact_id: "repository-draft-md-2-format-1", input_sha256: digest("d"), author_artifact_id: null, author_sha256: null,
          outputs: { pdf: { artifact_id: "repository-draft-pdf-2-format-1", sha256: digest("a"), conversion_artifact_id: "repository-draft-pdf-2-format-1-conversion" },
            docx: { artifact_id: "repository-draft-docx-2-format-1", sha256: digest("a"), conversion_artifact_id: "repository-draft-docx-2-format-1-conversion" } }, errors: [] }],
      } }] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state,
      { timeout: 60_000 }).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await selectView(page, "결과");
    const article = page.getByRole("article", { name: "publication-status", exact: true });
    const readiness = article.getByRole("region", { name: "원고 준비도", exact: true });
    await expect(readiness).toContainText("투고처 형식 보완 필요");
    await expect(readiness).toContainText("Actionable Insights");
    await expect(article).toContainText("과학적 검토 충족");
    await expect(article.getByRole('region', { name: '선택한 투고처', exact: true })).toContainText('IEEE Software');
    await article.getByText('두 IEEE 매체 적합성 비교', { exact: true }).click();
    for (const venue of PUBLICATION_VENUES) await expect(article.getByRole('region', { name: '선택한 투고처', exact: true }))
      .toContainText(venue.name);
    const analysis = article.getByRole('region', { name: '실제 소스 분석 결과', exact: true });
    await expect(analysis).toContainText('실제 분석 · 1개 단위 · 1개 발견');
    await analysis.getByText('분석 기준과 실제 관측', { exact: true }).click();
    await expect(analysis).toContainText('unit-a · Synthetic bridge');
    await expect(analysis).toContainText('합성 관측은 명시한 호출 위치에 한정됩니다.');
    await expect(article.getByText("원고 생성·투고 요건 확인 필요", { exact: true })).toHaveCount(0);
    const feedback = article.getByLabel("투고 품질 보완 의견 (12~12,000자)", { exact: true });
    await article.getByRole("button", { name: "형식 보완 의견 넣기", exact: true }).click();
    await expect(feedback).toHaveValue(/Actionable Insights/);
    await expect(article.getByRole("button", { name: "의견 반영해 원고 보완", exact: true })).toBeEnabled();
    expect((await page.evaluate(() => window.paperFactory.researchSnapshot())).jobs).toEqual(research.jobs);
    await electronApp.evaluate(({ BrowserWindow }) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      const job = fixture.research.jobs[0]!;
      job.repositoryPaper!.draft!.sections.push({ heading: "Actionable Insights", text: "- Choose an explicit boundary.\n- Compare the supported alternatives.\n- Record the remaining tradeoff." });
      job.repositoryPaper!.venueFormat = { ...job.repositoryPaper!.venueFormat!, insights: 3, formatReady: true, blockers: [] };
      job.authorMetadata = { origin: "explicit_human_author_metadata", value: { display_name: "Synthetic Author",
        email: "fixture@example.invalid", affiliation: "Synthetic UI Institution" }, bindings: {}, scope: "Synthetic fixture only",
        artifact_id: "author-current", sha256: "b".repeat(64), selection_artifact_id: "author-selection" };
      job.artifacts.push({ id: "author-current", sha256: "b".repeat(64), size: 120 });
      BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", fixture.research);
    });
    await expect(readiness).toContainText("저자 정보 반영 출력 필요");
    await expect(article.getByText("현재 PDF·Word에 최신 저자 정보가 반영되었는지 확인되지 않았습니다.", { exact: false })).toBeVisible();
    const current = article.getByRole("region", { name: "현재 원고 출력", exact: true });
    await expect(current.getByRole("button", { name: "원고 2 · PDF · 출력 보완 1 열기", exact: true })).toBeVisible();
    const previous = article.getByRole("group", { name: "이전 출력 파일", exact: true });
    await expect(article.getByRole("button", { name: "원고 1 · PDF 열기", exact: true })).toBeHidden();
    await previous.locator("summary").click();
    await expect(previous.getByRole("button", { name: "원고 1 · PDF 열기", exact: true })).toBeVisible();
    await expect(article).toContainText("현재 원고의 출력 다시 생성: 2/3회 남음.");
    const retained = await page.evaluate(() => window.paperFactory.researchSnapshot());
    expect(retained.jobs[0]!.draftAttempt).toBe(2);
    expect(retained.jobs[0]!.executionAttempt).toBe(0);
    expect(retained.jobs[0]!.repositoryPaper!.review).toEqual(research.jobs[0]!.repositoryPaper!.review);
    expect(await electronApp.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls)).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("ieee-publication-status-current-output.png"), animations: "disabled", fullPage: true });
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
    interpretation: { passed: false, reason: "합성 입력 결과를 실제 앱 전체의 효과로 확대했습니다." }, presentation: passed,
    publication_readiness: {
      novelty: { passed: false, reason: "합성 UI 검사용 신규성 부족 사유입니다." },
      significance: { passed: false, reason: "합성 UI 검사용 중요성 부족 사유입니다." },
      validation: { passed: false, reason: "합성 UI 검사용 검증 범위 부족 사유입니다." },
      claim: "실제 연구 승인을 나타내지 않는 합성 UI 주장입니다.",
      scope: "합성 UI 화면에만 해당하는 유한 열거 범위입니다.",
      evidence_basis: "실제 실험이나 논문의 품질을 증명하지 않는 표시 fixture입니다.",
      evidence_mode: "finite_enumeration" as const, analysis_keys: [], fixture_labels: [], proof_section: null, proof_quote: null,
      closest_work: [{ source_id: "source-synthetic", excerpt_index: 0,
        quote: "실제 문헌이 아닌 화면 확인용 합성 인용문입니다. 본문 출처 인증이나 신규성 승인 근거로 사용할 수 없습니다.",
        known_result: "합성 UI의 알려진 결과 표시입니다.", difference: "합성 UI의 연구 차이 표시입니다." }],
    } };
  const base: Omit<ResearchSnapshot["jobs"][number], "id" | "source" | keyof ReturnType<typeof researchFixture>> = {
    goal: "검토 반려 이유 표시만 확인하는 합성 연구입니다.", model: "fixture-model", reviewerModel: "fixture-model",
    phase: "study-review", pipeline: "failed", stage: "proposed", status: "blocked", code: "STUDY_REJECTED",
    message: "합성 연구 설계 보류", updatedAt: "2026-01-01T00:00:00.000Z", artifacts: [], supportingDocuments: [],
    studyReview, manuscriptReview: null, resumeKind: null,
  };
  const research: ResearchSnapshot = { runtime: { state: "ready", message: "합성 품질 검토 fixture" }, busy: false,
    cleanupResearchIds: [], error: null, jobs: [
      { ...base, ...researchFixture("research-111111111111"), id: "research-111111111111", source: "https://github.com/fixture-owner/study-rejected",
        // Native state offers no preparation capability for a final structurally rejected proposal.
        resumeKind: null, proposalAttempt: 3, studyLiteratureAttempt: 2 },
      { ...base, ...researchFixture("research-222222222222"), id: "research-222222222222", source: "https://github.com/fixture-owner/manuscript-rejected",
        phase: "manuscript-review", stage: "manuscript", code: "MANUSCRIPT_REJECTED", message: "합성 원고 보류",
        studyReview: { ...studyReview, accepted: true, issues: [], contribution: passed, comparison: passed }, manuscriptReview,
        proposalAttempt: 2, studyLiteratureAttempt: 1, codeAttempt: 2, executionAttempt: 1, draftAttempt: 1, manuscriptAvailable: true },
      { ...base, ...researchFixture("research-333333333333"), id: "research-333333333333", source: "https://github.com/fixture-owner/retained-draft",
        phase: "idle", pipeline: "completed", stage: "exported", status: "completed", code: null, message: null,
        studyReview: null, proposalAttempt: 2, studyLiteratureAttempt: 1, codeAttempt: 1, executionAttempt: 1,
        draftAttempt: 3, manuscriptAvailable: true, artifacts: [{ id: "export-pdf", sha256: "a".repeat(64), size: 18 }] },
      { ...base, ...researchFixture("research-444444444444"), id: "research-444444444444", source: "https://github.com/fixture-owner/proposal-being-revised",
        pipeline: "running", message: "합성 제안 보완 중" },
      { ...base, ...researchFixture("research-555555555555"), id: "research-555555555555", source: "https://github.com/fixture-owner/retained-study-only",
        phase: "idle", pipeline: "completed", stage: "exported", status: "completed", code: null, message: null,
        studyReview: approvedStudyReview, manuscriptReview: null,
        artifacts: [{ id: "export-pdf", sha256: "a".repeat(64), size: 18 }] },
      { ...base, ...researchFixture("research-666666666666"), id: "research-666666666666", source: "https://github.com/fixture-owner/infeasible-study",
        phase: "plan", code: "STUDY_INFEASIBLE", message: "합성 연구 실행 가능성 보류", resumeKind: "preparation" },
      { ...base, ...researchFixture("research-777777777777"), id: "research-777777777777", source: "https://github.com/fixture-owner/contribution-candidate",
        proposalAttempt: 3, studyLiteratureAttempt: 2, redesignQuestionEvidenceCollections: 1,
        redesignQuestionSearchRepairPlans: 1, redesignQuestionSearchRepairCollections: 1,
        studyReview: { ...studyReview, publication_readiness: manuscriptReview.publication_readiness } },
      { ...base, ...researchFixture("research-888888888888"), id: "research-888888888888", source: "https://github.com/fixture-owner/review-without-manuscript",
        phase: "manuscript-review", manuscriptReview, draftAttempt: 1 },
      { ...base, ...researchFixture("research-999999999999"), id: "research-999999999999", source: "https://github.com/fixture-owner/submission-pending",
        phase: "idle", pipeline: "paused", stage: "exported", status: "ready", code: "SUBMISSION_PENDING",
        message: "합성 원고와 출력은 보존했으며 공식 투고 요건·화면 검수·저자 확인을 기다립니다.",
        studyReview: approvedStudyReview, manuscriptReview: approvedManuscriptReview,
        executionAttempt: 1, draftAttempt: 2, manuscriptAvailable: true,
        artifacts: [{ id: "export-pdf", sha256: "a".repeat(64), size: 18 }],
        submissionContract: { bindings: { research_id: "research-999999999999" }, scope: "합성 UI 계약이며 실제 투고 승인을 뜻하지 않습니다.", value: {
          article_type: "finite_enumeration", language: "한국어", target_audience: "합성 화면을 확인하는 연구자이며 실제 학술지 독자 적합성은 미검증입니다.",
          core_claim: "실험 전에 계획한 합성 기여이며 실제 관측으로 승인된 결론과 구분합니다.",
          claim_obligations: [{ id: "claim1", claim: "합성 입력의 유한 비교 범위에서 결론을 정당화해야 합니다.", validation_mode: "finite_enumeration",
            required_evidence: "보존된 합성 관측·독립 비교·직접 관련 본문 근거가 필요합니다.", importance: "합성 UI 표시만 확인하며 실제 신규성이나 중요성을 승인하지 않습니다." }],
          venue_candidates: [{ name: "합성 미검증 학술지 후보", rationale: "모델 제안 표시만 확인하며 실제 공식 학술지 규정을 확인하지 않았습니다.", official_requirements_status: "pending", official_requirements: [] }], selected_venue: null } },
        plannedClaim: { mode: "finite_enumeration", claim: "계획한 긍정 효과는 관측 전의 합성 가설입니다.", scope: "원래 선언한 합성 유한 입력과 비교 정책에만 적용하는 범위입니다." },
        manuscriptClaim: { bindings: { research_id: "research-999999999999" }, scope: "합성 실제 결론 표시입니다.", value: {
          mode: "finite_enumeration", claim: "보존된 합성 관측에서는 계획한 긍정 효과를 확인하지 못했습니다.", scope: "합성 유한 입력과 비교 정책에만 적용하는 범위입니다.",
          outcome: "negative", scope_justification: "합성 관측의 범위로 결론을 제한했으며 계획 가설을 사실로 바꾸지 않았습니다.",
          analysis_keys: ["synthetic.condition_1.mean"], fixture_labels: [], proof_section: null, proof_quote: null } },
        submissionReadiness: { ready: false, status: "venue_pending", science_verified: true, venue_verified: false,
          formats_verified: true, visual_verified: false, author_verified: false,
          blockers: ["공식 투고처 요건을 확인해야 합니다.", "PDF 화면 검수와 저자 확인이 필요합니다."] },
        researchLedger: { entries: [{ event: "원고 반려 후 보완 기록", failed_criteria: ["interpretation"], repeated_failure: true,
          stop_required: true, reason: "합성 원고의 같은 주장 범위 결함을 보존하고 실제 변경 없이 다시 쓰지 않습니다." }] } },
    ] };
  try {
    electronApp = await launch(dataDir);
    const page = await electronApp.firstWindow();
    await expect.poll(async () => (await page.evaluate(() => window.paperFactory.researchSnapshot())).runtime.state, { timeout: 60_000 }).not.toBe("checking");
    await installGateFixture(electronApp, connection, research);
    await selectView(page, "결과");
    const rejectedStudy = page.getByRole("article", { name: "study-rejected", exact: true });
    await expect(rejectedStudy.getByText("연구 보류", { exact: true })).toBeVisible();
    await expect(rejectedStudy).toContainText("연구 적합성 검토 (study-review)");
    await expect(rejectedStudy.getByText("새로운 기여 · 미충족", { exact: true })).toBeVisible();
    await expect(rejectedStudy.getByText(studyReview.contribution.reason, { exact: true })).toBeVisible();
    await expect(rejectedStudy.getByText(studyReview.comparison.reason, { exact: true })).toBeVisible();
    await expect(rejectedStudy.getByText("이 기록에는 신규성·기여의 중요성·검증 범위를 평가한 연구 기여 가능성 검토가 없습니다.", { exact: true })).toBeVisible();
    const counts = rejectedStudy.getByRole("region", { name: "연구 진행 횟수", exact: true });
    await expect(counts).toContainText("정식 설계 제출: 3/3회");
    await expect(counts).toContainText("문헌 보완: 2/3회");
    await expect(counts).toContainText("질문 근거 회수: 0/1회");
    await expect(counts).toContainText("검색 보완 계획: 0/1회");
    await expect(counts).toContainText("검색 보완 회수: 0/1회");
    await expect(counts).toContainText("새 질문 제안: 0/1회");
    await expect(counts).toContainText("새 질문 독립 비교: 0/1회");
    await expect(counts).toContainText("과학실험 실행: 0/1회");
    await expect(counts).toContainText("원고 작성: 0회");
    await expect(counts).toContainText("연구 설계 보완: 0/2회");
    const unusedQuestionEvidenceCounts = await counts.textContent();
    await expect(rejectedStudy.getByText("아직 실제 원고가 없습니다. 투고 준비도는 원고 작성 후 평가합니다.", { exact: true })).toBeVisible();
    await expect(rejectedStudy.getByRole("region", { name: "실제 원고 투고 준비도", exact: true })).toHaveCount(0);
    await expect(rejectedStudy.getByRole("button")).toHaveCount(0);
    const infeasibleStudy = page.getByRole("article", { name: "infeasible-study", exact: true });
    await expect(infeasibleStudy.getByText("연구 보류", { exact: true })).toBeVisible();
    await expect(infeasibleStudy.getByText("실패", { exact: true })).toHaveCount(0);
    await expect(infeasibleStudy.getByText("현재 설계의 근거가 부족해 실험과 원고 생성을 진행하지 않았습니다. 검토 이유와 이어갈 수 있는 보완 작업을 확인하세요.", { exact: true })).toBeVisible();
    await expect(infeasibleStudy.getByText("합성 연구 실행 가능성 보류", { exact: true })).toBeVisible();
    await expect(infeasibleStudy.getByRole("button")).toHaveCount(0);
    const rejectedManuscript = page.getByRole("article", { name: "manuscript-rejected", exact: true });
    await expect(rejectedManuscript.getByText("원고 보류", { exact: true })).toBeVisible();
    await expect(rejectedManuscript.getByText(manuscriptReview.interpretation.reason, { exact: true })).toBeVisible();
    const readiness = rejectedManuscript.getByRole("region", { name: "실제 원고 투고 준비도", exact: true });
    await expect(readiness.getByText("선행 연구 대비 신규성 · 미충족", { exact: true })).toBeVisible();
    await expect(readiness.getByText("기여의 중요성 · 미충족", { exact: true })).toBeVisible();
    await expect(readiness.getByText("주장 범위에 맞는 검증 · 미충족", { exact: true })).toBeVisible();
    await readiness.getByText("직접 관련 선행 연구 비교 1", { exact: true }).click();
    await expect(readiness.getByText(manuscriptReview.publication_readiness.closest_work[0].quote, { exact: true })).toBeVisible();
    await expect(rejectedManuscript.getByRole("button")).toHaveCount(0);
    const manuscriptCounts = rejectedManuscript.getByRole("region", { name: "연구 진행 횟수", exact: true });
    await expect(manuscriptCounts).toContainText("실험 코드 작성: 2회");
    await expect(manuscriptCounts).toContainText("과학실험 실행: 1/1회");
    await expect(manuscriptCounts).toContainText("원고 작성: 1회");
    const candidate = page.getByRole("article", { name: "contribution-candidate", exact: true });
    const candidateCounts = candidate.getByRole("region", { name: "연구 진행 횟수", exact: true });
    await expect(candidateCounts).toContainText("질문 근거 회수: 1/1회");
    await expect(candidateCounts).toContainText("검색 보완 계획: 1/1회");
    await expect(candidateCounts).toContainText("검색 보완 회수: 1/1회");
    await expect(candidateCounts).toContainText("정식 설계 제출: 3/3회");
    await expect(candidateCounts).toContainText("문헌 보완: 2/3회");
    await expect(candidateCounts).toContainText("과학실험 실행: 0/1회");
    const usedQuestionEvidenceCounts = await candidateCounts.textContent();
    await expect(candidate.getByRole("region", { name: "연구 기여 가능성 평가", exact: true })).toBeVisible();
    await expect(candidate.getByRole("region", { name: "실제 원고 투고 준비도", exact: true })).toHaveCount(0);
    await expect(candidate.getByText("설계의 신규성·중요성·예정된 검증 범위를 평가한 기록입니다. 실제 원고의 투고 준비도는 원고 작성 후 평가합니다.", { exact: true })).toBeVisible();
    const reviewWithoutManuscript = page.getByRole("article", { name: "review-without-manuscript", exact: true });
    await expect(reviewWithoutManuscript.getByRole("region", { name: "원고 검토 기록", exact: true })).toBeVisible();
    await expect(reviewWithoutManuscript.getByRole("region", { name: "실제 원고 투고 준비도", exact: true })).toHaveCount(0);
    await expect(reviewWithoutManuscript.getByText("아직 실제 원고가 없습니다. 투고 준비도는 원고 작성 후 평가합니다.", { exact: true })).toBeVisible();
    const retainedDraft = page.getByRole("article", { name: "retained-draft", exact: true });
    await expect(retainedDraft.getByText("보존된 원고·투고 확인 필요", { exact: true })).toBeVisible();
    await expect(retainedDraft.getByText("투고 준비 완료", { exact: true })).toHaveCount(0);
    await expect(retainedDraft.getByRole("region", { name: "연구 진행 횟수", exact: true })).toContainText("원고 작성: 3회");
    await expect(retainedDraft.getByText("실제 원고가 보존되어 있습니다. 원고 검토 결과에서 투고 준비도를 확인하세요.", { exact: true })).toBeVisible();
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
    const pendingSubmission = page.getByRole("article", { name: "submission-pending", exact: true });
    await expect(pendingSubmission.getByText("투고처·원고 검수 대기", { exact: true })).toBeVisible();
    await expect(pendingSubmission.getByText("투고 준비 완료", { exact: true })).toHaveCount(0);
    const target = pendingSubmission.getByRole("region", { name: "저장된 투고 목표", exact: true });
    await expect(target).toContainText("미검증 투고처 후보"); await expect(target).toContainText("공식 요건 확인 대기");
    const observed = pendingSubmission.getByRole("region", { name: "계획 가설과 실제 관측 결론", exact: true });
    await expect(observed).toContainText("계획한 긍정 효과는 관측 전의 합성 가설입니다.");
    await expect(observed).toContainText("실제 결론 (부정 결과)"); await expect(observed).toContainText("긍정 효과를 확인하지 못했습니다.");
    const finalGates = pendingSubmission.getByRole("region", { name: "실제 투고 완료 조건", exact: true });
    await expect(finalGates).toContainText("투고처 공식 요건: 대기"); await expect(finalGates).toContainText("출력 화면 검수: 대기");
    await expect(finalGates).toContainText("저자 확인: 대기"); await expect(finalGates).toContainText("과학 근거·원고: 확인");
    const humanChecks = pendingSubmission.getByRole("region", { name: "사용자 투고 검수", exact: true });
    await expect(humanChecks).toHaveCount(0);
    await expect(pendingSubmission.getByRole("button", { name: "PDF 열기", exact: true })).toBeVisible();
    await pendingSubmission.getByText("누적 판단·보완 기록 1개", { exact: true }).click();
    await expect(pendingSubmission).toContainText("동일한 실패가 반복되었습니다.");
    await expect(pendingSubmission).toContainText("실제 변경이나 새 근거 없이 같은 원고를 반복하지 않습니다.");
    const captureWindow = await electronApp.browserWindow(page);
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    for (const [article, name] of [["study-rejected", "quality-review-rejections"],
      ["manuscript-rejected", "quality-manuscript-rejection"], ["retained-draft", "quality-retained-draft"],
      ["contribution-candidate", "quality-contribution-candidate"], ["submission-pending", "quality-submission-pending"]] as const) {
      await page.getByRole("article", { name: article, exact: true }).evaluate(element => element.scrollIntoView({ block: "start" }));
      await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
      const png = await captureWindow.evaluate(async (window) => {
        const image = await window.webContents.capturePage(undefined, { stayHidden: true });
        if (window.isVisible() || image.isEmpty()) throw new Error("Offscreen quality fixture capture failed.");
        return image.toPNG().toString("base64");
      });
      await writeFile(testInfo.outputPath(`${name}.png`), Buffer.from(png, "base64"));
    }
    expect(await electronApp.evaluate(() =>
      (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture.forbiddenCalls)).toEqual([]);
    expect((await page.evaluate(() => window.paperFactory.researchSnapshot())).jobs).toEqual(research.jobs);
    const searchRepairStages: Array<{ phase: string; text: string | null }> = [];
    for (const phase of ["question-search-plan", "question-literature"] as const) {
      const progress = structuredClone(research);
      const progressJob = progress.jobs.find(job => job.id === "research-777777777777")!;
      progressJob.phase = phase; progressJob.pipeline = "running";
      progressJob.redesignQuestionSearchRepairCollections = phase === "question-search-plan" ? 0 : 1;
      await electronApp.evaluate(({ BrowserWindow }, research) => {
        const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
        fixture.research = research; BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", research);
      }, progress);
      await expect(candidate).toContainText(phase === "question-search-plan"
        ? "검색 실패 보완 계획 (question-search-plan)" : "질문 근거 회수 (question-literature)");
      await expect(candidateCounts).toContainText("검색 보완 계획: 1/1회");
      await expect(candidateCounts).toContainText(`검색 보완 회수: ${phase === "question-search-plan" ? 0 : 1}/1회`);
      await expect(candidateCounts).toContainText("질문 근거 회수: 1/1회");
      await expect(candidateCounts).toContainText("정식 설계 제출: 3/3회");
      await expect(candidateCounts).toContainText("문헌 보완: 2/3회");
      await expect(candidateCounts).toContainText("과학실험 실행: 0/1회");
      searchRepairStages.push({ phase, text: await candidate.textContent() });
    }
    const questionReframingStages: Array<{ status: string; text: string | null }> = [];
    for (const [status, comparisonCount, text] of [
      ["planning", 0, "보류된 기존 질문과 보존된 원문을 바탕으로, 실질적으로 다른 새 연구 질문을 제안하고 있습니다."],
      ["proposed", 0, "새 연구 질문 제안을 보존했습니다. 독립 비교에서 연구 기여·중요성·검증 가능성을 판단할 차례입니다."],
      ["reviewing", 1, "제안된 새 질문을 기존 질문·설계 및 보존된 원문과 독립 비교하고 있습니다."],
      ["ready", 1, "독립 비교에서 새 질문을 후보 작성 대상으로 선택했습니다. 별도 연구 설계와 적합성 검토가 이어집니다."],
      ["held", 1, "이번 질문 보완에서도 근거를 갖춘 후속 후보를 선택하지 못했습니다. 보류 판정과 필요한 근거를 보존했습니다."],
      ["incomplete", 0, "새 질문의 제안 또는 독립 비교를 완료하지 못했습니다. 기존 보류 판정과 이번 시도 기록을 보존했습니다."],
    ] as const) {
      const progress = structuredClone(research);
      const progressJob = progress.jobs.find(job => job.id === "research-777777777777")!;
      progressJob.phase = comparisonCount ? "question-reframing-selection" : "question-reframing";
      progressJob.pipeline = status === "held" || status === "incomplete" ? "failed" : "running";
      progressJob.code = status === "held" || status === "incomplete" ? "QUESTION_SELECTION_HELD" : "STUDY_REJECTED";
      progressJob.redesignQuestionReframingPlans = 1;
      progressJob.redesignQuestionReframingComparisons = comparisonCount;
      progressJob.redesignQuestionReframingStatus = status;
      await electronApp.evaluate(({ BrowserWindow }, research) => {
        const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
        fixture.research = research; BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", research);
      }, progress);
      await expect(candidate).toContainText(comparisonCount
        ? "새 연구 질문 독립 비교 (question-reframing-selection)" : "새 연구 질문 제안 (question-reframing)");
      const reframing = candidate.getByRole("region", { name: "새 연구 질문 검토", exact: true });
      await expect(reframing.getByText(text, { exact: true })).toBeVisible();
      await expect(reframing).toContainText("기존 질문과 보류 판정은 그대로 보존됩니다.");
      await expect(candidateCounts).toContainText("새 질문 제안: 1/1회");
      await expect(candidateCounts).toContainText(`새 질문 독립 비교: ${comparisonCount}/1회`);
      await expect(candidateCounts).toContainText("정식 설계 제출: 3/3회");
      await expect(candidateCounts).toContainText("문헌 보완: 2/3회");
      await expect(candidateCounts).toContainText("질문 근거 회수: 1/1회");
      await expect(candidateCounts).toContainText("검색 보완 계획: 1/1회");
      await expect(candidateCounts).toContainText("검색 보완 회수: 1/1회");
      await expect(candidateCounts).toContainText("과학실험 실행: 0/1회");
      await expect(candidate.getByText("아직 실제 원고가 없습니다. 투고 준비도는 원고 작성 후 평가합니다.", { exact: true })).toBeVisible();
      await expect(candidate.getByRole("region", { name: "실제 원고 투고 준비도", exact: true })).toHaveCount(0);
      if (status === "held" || status === "incomplete") {
        await expect(candidate.getByText("연구 보류", { exact: true })).toBeVisible();
        await expect(candidate.getByText("실패", { exact: true })).toHaveCount(0);
        await expect(candidate.getByText("투고 준비 완료", { exact: true })).toHaveCount(0);
        await expect(candidate.getByRole("button", { name: "심사·보완 이어가기", exact: true })).toHaveCount(0);
        await expect(candidate.getByRole("button", { name: "연구 준비 재개", exact: true })).toHaveCount(0);
      }
      if (status === "held") {
        await candidateCounts.evaluate(element => element.scrollIntoView({ block: "start" }));
        await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
        const png = await captureWindow.evaluate(async window => {
          const image = await window.webContents.capturePage(undefined, { stayHidden: true });
          if (window.isVisible() || image.isEmpty()) throw new Error("Question reframing fixture must remain offscreen.");
          return image.toPNG().toString("base64");
        });
        await writeFile(testInfo.outputPath("question-reframing-held.png"), Buffer.from(png, "base64"), { flag: "wx" });
      }
      questionReframingStages.push({ status, text: await candidate.textContent() });
    }
    const cappedReframing = structuredClone(research);
    const cappedJob = cappedReframing.jobs.find(job => job.id === "research-777777777777")!;
    cappedJob.phase = "question-reframing-selection"; cappedJob.code = "STUDY_REDESIGN_LIMIT";
    cappedJob.redesignAttempt = 2; cappedJob.redesignQuestionReframingPlans = 1;
    cappedJob.redesignQuestionReframingComparisons = 1; cappedJob.redesignQuestionReframingStatus = "held";
    await electronApp.evaluate(({ BrowserWindow }, research) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      fixture.research = research; BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", research);
    }, cappedReframing);
    await expect(candidate.getByText("연구 보류", { exact: true })).toBeVisible();
    await expect(candidate.getByText("실패", { exact: true })).toHaveCount(0);
    await expect(candidateCounts).toContainText("연구 설계 보완: 2/2회");
    await expect(candidateCounts).toContainText("새 질문 제안: 1/1회");
    await expect(candidateCounts).toContainText("새 질문 독립 비교: 1/1회");
    await expect(candidate.getByRole("button", { name: "심사·보완 이어가기", exact: true })).toHaveCount(0);
    await expect(candidate.getByText("아직 실제 원고가 없습니다. 투고 준비도는 원고 작성 후 평가합니다.", { exact: true })).toBeVisible();
    const unverified: ResearchSnapshot = { ...research, runtime: { state: "unavailable", message: "합성 연구 기록 미확인 상태" },
      jobs: [{ ...research.jobs[0]!, proposalAttempt: null, studyLiteratureAttempt: null, codeAttempt: null,
        executionAttempt: null, draftAttempt: null, redesignAttempt: null, preparationRepairAttempt: null,
        redesignQuestionEvidenceCollections: null, redesignQuestionSearchRepairPlans: null,
        redesignQuestionSearchRepairCollections: null, redesignQuestionReframingPlans: null,
        redesignQuestionReframingComparisons: null, redesignQuestionReframingStatus: null, manuscriptAvailable: null }] };
    await electronApp.evaluate(({ BrowserWindow }, research) => {
      const fixture = (globalThis as typeof globalThis & { __paperFactoryGateFixture: GateFixture }).__paperFactoryGateFixture;
      fixture.research = research;
      BrowserWindow.getAllWindows()[0]?.webContents.send("research:changed", research);
    }, unverified);
    const unverifiedCounts = rejectedStudy.getByRole("region", { name: "연구 진행 횟수", exact: true });
    await expect(unverifiedCounts.getByText("미확인", { exact: true })).toHaveCount(14);
    await expect(unverifiedCounts).not.toContainText("undefined");
    await expect(unverifiedCounts).not.toContainText("0/1회");
    await writeFile(testInfo.outputPath("question-evidence-counts.json"), JSON.stringify({
      scope: "Isolated synthetic UI fixture; no actual study, scientific model or execution evidence",
      unused: unusedQuestionEvidenceCounts, used: usedQuestionEvidenceCounts,
      searchRepairStages, questionReframingStages,
      unverified: await unverifiedCounts.textContent(),
      windows: await electronApp.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().map(window => ({
        visible: window.isVisible(), offscreen: window.webContents.isOffscreen(),
      }))),
    }, null, 2), { encoding: "utf8", flag: "wx" });
    await expect(rejectedStudy.getByText("원고 확인 필요: 연구 기록을 확인한 뒤 실제 원고 유무를 표시합니다.", { exact: true })).toBeVisible();
    await expect(rejectedStudy.getByText("아직 실제 원고가 없습니다. 투고 준비도는 원고 작성 후 평가합니다.", { exact: true })).toHaveCount(0);
    expect((await page.evaluate(() => window.paperFactory.researchSnapshot())).jobs).toEqual(unverified.jobs);
  } finally {
    if (electronApp) await electronApp.close();
    await removeOwnedTemp(dataDir);
  }
});
