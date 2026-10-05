import { _electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import type { AppSnapshot, PaperFactoryApi } from "../src/shared/contracts";
import type { ResearchSnapshot } from "../src/shared/research";

declare global {
  interface Window {
    paperFactory: PaperFactoryApi;
  }
}

const desktopRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
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
  return _electron.launch({ args: [desktopRoot], cwd: desktopRoot, env, timeout: 30_000 });
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
      "addResearchEvidence", "cancel", "cancelResearch", "checkRuntime", "createResearch", "disconnect", "listPublicRepositories", "onResearchSnapshot", "onSnapshot",
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
    }
    for (const destination of ["", "relative/paper.pdf", "bad\u0000path", "x".repeat(4097)]) {
      expect(await page.evaluate(async path => {
        try { await window.paperFactory.saveArtifact("research-abcdef123456", "export-pdf", path); return false; }
        catch { return true; }
      }, destination)).toBe(true);
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
    await electronApp.evaluate(async ({ BrowserWindow, ipcMain, shell }, { snapshot, research, artifactModule, protectedRoot }) => {
      const { validateSaveDestination, writeArtifactCopy } = process.getBuiltinModule('module').createRequire(artifactModule)('./artifacts.js');
      const fixture = { snapshot, research, verifyCalls: 0, researchCalls: 0, revisions: [] as string[][], saves: [] as string[][], openedUrls: [] as string[] };
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
      ipcMain.removeHandler("research:save-artifact");
      ipcMain.handle("research:save-artifact", async (_event, id: string, artifactId: string, path: string) => {
        const destination = validateSaveDestination(path);
        const job = fixture.research.jobs.find(job => job.id === id);
        if (!job || job.status !== "completed" || !job.artifacts.some(artifact => artifact.id === artifactId)) throw new Error("Unexpected fixture artifact");
        await writeArtifactCopy(Buffer.from("OWNED SYNTHETIC " + artifactId), destination, protectedRoot);
        fixture.saves.push([id, artifactId, destination]);
        return true;
      });
      ipcMain.removeHandler("research:revise-writing");
      ipcMain.handle("research:revise-writing", (_event, id: string, model: string, reviewer: string) => {
        const job = fixture.research.jobs.find(job => job.id === id);
        if (!job || job.stage !== "exported" || job.status !== "completed" || fixture.research.busy) throw new Error("Unexpected fixture revision");
        fixture.revisions.push([id, model, reviewer]);
        fixture.research = { ...fixture.research, busy: true, jobs: fixture.research.jobs.map(current => current.id === id
          ? { ...current, stage: "analyzed", status: "ready", pipeline: "running", phase: "manuscript", model, reviewerModel: reviewer } : current) };
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
    }, { snapshot: fixtureSnapshot, research: fixtureResearch, artifactModule: new URL("../dist/artifacts.js", import.meta.url).href, protectedRoot: dataDir });
    const inspectFixture = () => electronApp!.evaluate(() => {
      const fixture = (globalThis as typeof globalThis & {
        __paperFactoryCreditFixture: { verifyCalls: number; researchCalls: number; revisions: string[][]; saves: string[][]; openedUrls: string[]; snapshot: AppSnapshot };
      }).__paperFactoryCreditFixture;
      return { verifyCalls: fixture.verifyCalls, researchCalls: fixture.researchCalls,
        revisions: fixture.revisions, saves: fixture.saves, openedUrls: fixture.openedUrls, profileId: fixture.snapshot.session.profileId };
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
      model: "fixture-model", reviewerModel: "fixture-model", phase: "idle", pipeline: "completed",
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
    const markdownSave = page.getByRole("button", { name: "Markdown 저장", exact: true });
    await expect(markdownSave).toBeVisible();
    await markdownSave.click();
    const saveDialog = page.getByRole("dialog", { name: "Markdown 저장", exact: true });
    await expect(saveDialog).toBeVisible();
    await expect(saveDialog.getByLabel("저장 파일 경로", { exact: true })).toBeFocused();
    await expect(saveDialog.getByRole("button", { name: "저장", exact: true })).toBeDisabled();
    await saveDialog.getByRole("button", { name: "취소", exact: true }).click();
    await expect(saveDialog).toHaveCount(0); await expect(markdownSave).toBeFocused();
    expect((await inspectFixture()).saves).toEqual([]);
    // These five files contain only harmless synthetic bytes; they are not actual research outputs.
    for (const [artifactId, label] of [["export-pdf", "PDF"], ["export-docx", "Word"], ["export-md", "Markdown"], ["export-tex", "LaTeX"], ["reproducibility", "재현 패키지 ZIP"]]) {
      const trigger = page.getByRole("button", { name: label + " 저장", exact: true });
      await trigger.click();
      const popup = page.getByRole("dialog", { name: label + " 저장", exact: true });
      const pathInput = popup.getByLabel("저장 파일 경로", { exact: true });
      await expect(pathInput).toBeFocused();
      if (artifactId === "export-pdf") {
        await pathInput.fill("relative/paper.pdf");
        await popup.getByRole("button", { name: "저장", exact: true }).click();
        await expect(popup.getByRole("alert")).toContainText("저장하지 못했습니다");
        await expect(pathInput).toBeEnabled(); expect((await inspectFixture()).saves).toEqual([]);
      }
      const destination = join(tmpdir(), basename(dataDir) + "-" + artifactId + ".bin");
      try {
        await pathInput.fill(destination);
        if (artifactId === "export-pdf") await page.screenshot({ path: testInfo.outputPath("internal-save-path-modal.png"), animations: "disabled", fullPage: true });
        await popup.getByRole("button", { name: "저장", exact: true }).click();
        await expect(popup).toHaveCount(0); await expect(trigger).toBeFocused();
        await expect(page.getByRole("tabpanel", { name: "결과", exact: true }).getByText("결과 파일을 저장했습니다.", { exact: true })).toBeVisible();
        expect(await readFile(destination)).toEqual(Buffer.from("OWNED SYNTHETIC " + artifactId));
      } finally { await rm(destination, { force: true }); }
    }
    expect((await inspectFixture()).saves).toHaveLength(5);
    await page.getByText("재개·원고 수정에 사용할 모델", { exact: true }).click();
    await expect(page.getByRole("combobox", { name: "재개 작성 모델", exact: true })).toContainText("Fixture writer");
    await expect(page.getByRole("combobox", { name: "재개 리뷰 모델", exact: true })).toContainText("Fixture reviewer");
    const revision = page.getByRole("button", { name: "원고 수정", exact: true });
    await expect(revision).toBeEnabled(); expect((await inspectFixture()).revisions).toEqual([]);
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
      jobs: [{ id: "synthetic-busy-receipt", source: draftSource, goal: draftGoal, supportingDocuments: [],
        model: "fixture-writer", reviewerModel: "fixture-reviewer", phase: "plan", pipeline: "running",
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
  const dataDir = await mkdtemp(join(tmpdir(), "paper-factory-electron-"));
  const fixtureText = "Paper Factory safeStorage test fixture: contains no credentials.";
  const fixturePath = join(dataDir, "safe-storage-fixture.bin");
  let electronApp: ElectronApplication | undefined;
  try {
    electronApp = await test.step("launch first isolated app", () => launch(dataDir));
    const firstPage = await test.step("wait for first isolated window", () => electronApp!.firstWindow());
    await test.step("wait for first app startup to finish before requesting quit", () =>
      expect(firstPage.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeEnabled());
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
      expect(page.getByRole("button", { name: "Continue with ChatGPT", exact: true })).toBeEnabled());
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
