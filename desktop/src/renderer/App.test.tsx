import "./test-setup";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import type { AgentStatus, Connection, DesktopBridge, Pipeline, Project } from "./model";

function fixture(
  options: {
    connection?: Connection;
    projects?: Project[];
    tools?: AgentStatus["tools"];
    error?: string;
    providerReady?: boolean;
  } = {},
) {
  let connection = options.connection ?? {
    status: "available",
    model_available: true,
    connected: true,
    authentication: "chatgpt",
  };
  const projects = options.projects ?? [];
  const request = vi.fn(async (method: "GET" | "POST", path: string) => {
    if (options.error && method === "GET") throw new Error(options.error);
    if (method === "GET") {
      if (path === "/api/agent/status")
        return {
          provider: { ready: options.providerReady ?? true, executable_available: true },
          runner: { ready: true },
          tools: options.tools ?? { git: true, pandoc: true },
        };
      if (path === "/api/agent/connection") return connection;
      if (path === "/api/projects") return { projects };
      if (path === "/api/jobs") return { jobs: [] };
      if (path === "/api/studies") return { studies: [] };
      if (path.startsWith("/api/projects/"))
        return projects.find((project) => path === `/api/projects/${project.id}`);
    }
    if (path === "/api/agent/connection/logout") {
      connection = { status: "logged_out", model_available: false, connected: false };
      return connection;
    }
    if (path === "/api/agent/connection/login") return { status: "starting" };
    if (path === "/api/agent/connection/probe") return { status: "probing" };
    if (path === "/api/agent/repositories")
      return {
        repositories: [
          {
            name: "owner/repo",
            url: "https://github.com/owner/repo",
            reason: "테스트 가능한 동작이 있습니다.",
          },
        ],
        considered: 8,
        limitations: ["Only public repositories were inspected."],
      };
    return {};
  });
  const api: DesktopBridge = {
    request: request as DesktopBridge["request"],
    getRuntimeInfo: vi.fn(async () => ({
      version: "0.9.0",
      platform: "win32",
      backend: "ready" as const,
    })),
    openExternal: vi.fn(async () => {}),
    openArtifact: vi.fn(async () => {}),
    saveArtifact: vi.fn(async () => ({ canceled: false })),
  };
  return { api, request };
}
const run = (override: Partial<Pipeline> = {}): Pipeline => ({
  id: "pipeline-a",
  goal: "캐시 적용 전후의 응답 시간을 비교합니다",
  status: "running",
  stage: "execute",
  model_calls: 3,
  elapsed_seconds: 100,
  budget: { max_model_calls: 12, wall_seconds: 3600 },
  attempts: [
    { stage: "assess", status: "completed" },
    { stage: "plan", status: "completed" },
  ],
  ...override,
});
const project = (pipeline: Pipeline): Project => ({
  id: "web-a",
  name: "owner/repo",
  source: "https://github.com/owner/repo",
  status: "ready",
  pipelines: [pipeline],
});
async function ready() {
  await screen.findByText("사용 준비 완료");
}
function fillStudy() {
  fireEvent.change(screen.getByLabelText("GitHub 저장소"), {
    target: { value: "https://github.com/owner/repo" },
  });
  fireEvent.change(screen.getByLabelText("연구 목표"), {
    target: { value: "캐시 적용 전후의 응답 시간을 비교합니다" },
  });
}

describe("desktop automatic study flow through the restricted bridge", () => {
  it("starts an imported repository with a bounded autonomous goal only after explicit click", async () => {
    const { api, request } = fixture();
    render(<App api={api} />);
    await ready();
    expect(request.mock.calls.some(([method]) => method === "POST")).toBe(false);
    fillStudy();
    await userEvent.click(screen.getByRole("button", { name: "연구 시작하기" }));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith("POST", "/api/projects", {
        source: "https://github.com/owner/repo",
        autonomous: {
          goal: "캐시 적용 전후의 응답 시간을 비교합니다",
          budget: { max_model_calls: 12, wall_seconds: 3600 },
        },
      }),
    );
    expect(screen.getByRole("heading", { name: "진행 현황." })).toBeInTheDocument();
  });
  it("starts research on an existing ready project instead of reimporting it", async () => {
    const { api, request } = fixture({
      projects: [{ id: "web-a", name: "owner/repo", status: "ready" }],
    });
    render(<App api={api} />);
    await ready();
    fireEvent.change(screen.getByLabelText("프로젝트 선택"), { target: { value: "web-a" } });
    fireEvent.change(screen.getByLabelText("연구 목표"), {
      target: { value: "메모리 사용량의 변화를 비교합니다" },
    });
    await userEvent.click(screen.getByRole("button", { name: "연구 시작하기" }));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "POST",
        "/api/projects/web-a/pipelines",
        expect.objectContaining({ goal: "메모리 사용량의 변화를 비교합니다" }),
      ),
    );
  });
  it("blocks study execution after explicit logout even if provider reports an inherited ready login", async () => {
    const { api, request } = fixture({
      connection: { status: "logged_out", model_available: false },
    });
    render(<App api={api} />);
    await screen.findByRole("button", { name: "Codex 연결하기" });
    fillStudy();
    expect(screen.getByRole("button", { name: "연구 시작하기" })).toBeDisabled();
    expect(request.mock.calls.every(([method]) => method === "GET")).toBe(true);
  });
  it("shows the one-model-call probe after authentication and keeps research disabled until verified", async () => {
    const { api, request } = fixture({
      connection: {
        status: "authenticated",
        authentication: "chatgpt",
        model_available: false,
        connected: false,
        app_login_required: true,
        pending: {
          profile_id: "11111111111111111111111111111111",
          status: "authenticated",
          expires_at: null,
        },
      },
    });
    render(<App api={api} />);
    const button = await screen.findByRole("button", { name: "연결 확인 (1회 호출)" });
    expect(screen.getByText(/구독 사용량에 반영/)).toBeInTheDocument();
    fillStudy();
    expect(screen.getByRole("button", { name: "연구 시작하기" })).toBeDisabled();
    await userEvent.click(button);
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith("POST", "/api/agent/connection/probe", {}),
    );
  });
  it("opens only the fixed official device page through the bridge", async () => {
    const { api } = fixture({
      connection: {
        status: "waiting_user",
        user_code: "ABCD-EFGH",
        verification_url: "https://auth.openai.com/codex/device",
        app_login_required: true,
        connected: false,
        model_available: false,
        pending: {
          profile_id: "11111111111111111111111111111111",
          status: "waiting_user",
          expires_at: null,
        },
      },
    });
    render(<App api={api} />);
    await userEvent.click(await screen.findByRole("button", { name: "공식 로그인 페이지 열기" }));
    expect(api.openExternal).toHaveBeenCalledWith("https://auth.openai.com/codex/device");
    expect(screen.getByText("ABCD-EFGH")).toBeInTheDocument();
    expect(screen.getByText("공식 로그인 페이지에서 아래 코드를 입력하세요.")).toBeInTheDocument();
  });
  it("refuses a device page supplied by an untrusted URL", async () => {
    const { api } = fixture({
      connection: {
        status: "waiting_user",
        user_code: "ABCD-EFGH",
        verification_url: "https://evil.test/login",
      },
    });
    render(<App api={api} />);
    expect(await screen.findByRole("button", { name: "공식 로그인 페이지 열기" })).toBeDisabled();
    expect(api.openExternal).not.toHaveBeenCalled();
  });
  it("blocks research when Git is missing and explains the prerequisite", async () => {
    const { api } = fixture({ tools: { git: false, pandoc: true } });
    render(<App api={api} />);
    await ready();
    fillStudy();
    expect(screen.getByText(/Git을 찾지 못했습니다/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "연구 시작하기" })).toBeDisabled();
  });
  it("requires current state before logout and routes active research to progress", async () => {
    const { api, request } = fixture({ projects: [project(run())] });
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    const dialog = await screen.findByRole("dialog", { name: "Codex에서 로그아웃할까요?" });
    expect(within(dialog).getByText("진행 중인 연구를 먼저 종료해 주세요")).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "로그아웃" })).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "진행 현황 보기" }));
    expect(request).not.toHaveBeenCalledWith("POST", "/api/agent/connection/logout", {});
    expect(await screen.findByRole("button", { name: "연구 중지" })).toBeInTheDocument();
  });
  it("uses genuine logout rather than deleting a connection selection pointer", async () => {
    const { api, request } = fixture();
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    const dialog = await screen.findByRole("dialog", { name: "Codex에서 로그아웃할까요?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "로그아웃" }));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith("POST", "/api/agent/connection/logout", {}),
    );
    expect(await screen.findByText("로그아웃했습니다")).toBeInTheDocument();
    expect(request.mock.calls.some(([, path]) => path.endsWith("/disconnect"))).toBe(false);
  });
  it("confirms cancellation and prevents repeated cancellation while cleanup is pending", async () => {
    const { api, request } = fixture({ projects: [project(run())] });
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "진행 현황" }));
    await userEvent.click(screen.getByRole("button", { name: "연구 중지" }));
    const dialog = await screen.findByRole("dialog", { name: "이 연구를 중지할까요?" });
    expect(request.mock.calls.every(([method]) => method === "GET")).toBe(true);
    await userEvent.click(within(dialog).getByRole("button", { name: "중지 요청" }));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "POST",
        "/api/projects/web-a/pipelines/pipeline-a/cancel",
        {},
      ),
    );
  });
  it("shows cancellation cleanup without issuing another cancel automatically", async () => {
    const { api, request } = fixture({
      projects: [project(run({ cancellation_requested: true }))],
    });
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "진행 현황" }));
    expect(screen.getByRole("button", { name: "종료 확인 중" })).toBeDisabled();
    expect(request.mock.calls.every(([method]) => method === "GET")).toBe(true);
  });
  it("resumes retained research using its current pipeline ID", async () => {
    const { api, request } = fixture({
      projects: [project(run({ status: "paused", code: "INTERRUPTED" }))],
    });
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "진행 현황" }));
    await userEvent.click(screen.getByRole("button", { name: "이어서 진행" }));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "POST",
        "/api/projects/web-a/pipelines/pipeline-a/resume",
        {},
      ),
    );
  });
  it("opens and saves final artifacts using IPC paths and excludes unsafe artifacts", async () => {
    const { api } = fixture({
      projects: [
        project(
          run({
            status: "completed",
            files: [
              {
                name: "paper.pdf",
                url: "/api/projects/web-a/files/autonomous/pipeline-a/exports/paper.pdf",
                size: 1024,
              },
              {
                name: "paper.docx",
                url: "/api/projects/web-a/files/autonomous/pipeline-a/exports/paper.docx",
              },
              {
                name: "reproducibility.zip",
                url: "/api/projects/web-a/files/autonomous/pipeline-a/exports/reproducibility.zip",
              },
              { name: "private.pdf", url: "https://evil.test/private.pdf" },
            ],
          }),
        ),
      ],
    });
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "논문 보관함" }));
    expect(screen.getAllByRole("button", { name: "논문 PDF 열기" })).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "논문 PDF 열기" }));
    await waitFor(() =>
      expect(api.openArtifact).toHaveBeenCalledWith(
        "/api/projects/web-a/files/autonomous/pipeline-a/exports/paper.pdf",
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "전체 재현 자료 저장" }));
    await waitFor(() =>
      expect(api.saveArtifact).toHaveBeenCalledWith(
        "/api/projects/web-a/files/autonomous/pipeline-a/exports/reproducibility.zip",
      ),
    );
  });
  it("loads library emptiness without fabricating a completed paper", async () => {
    const { api } = fixture();
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "논문 보관함" }));
    expect(screen.getByRole("heading", { name: "첫 논문이 놓일 자리입니다" })).toBeInTheDocument();
  });
  it("filters stored research and preserves the search across navigation", async () => {
    const imported = project(run({ status: "completed" }));
    imported.pipelines!.push(
      run({ id: "pipeline-b", status: "completed", goal: "정렬 알고리즘의 메모리를 비교합니다" }),
    );
    const { api } = fixture({ projects: [imported] });
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "논문 보관함" }));
    fireEvent.change(screen.getByLabelText("논문 검색"), { target: { value: "캐시" } });
    expect(screen.getByText("1개의 연구")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "정렬 알고리즘의 메모리를 비교합니다" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "진행 현황" }));
    await userEvent.click(screen.getByRole("button", { name: "논문 보관함" }));
    expect(screen.getByLabelText("논문 검색")).toHaveValue("캐시");
    expect(screen.getByText("1개의 연구")).toBeInTheDocument();
  });
  it("handles unavailable backend readiness without leaving research enabled", async () => {
    const { api } = fixture({ error: "unavailable" });
    render(<App api={api} />);
    await screen.findByText("일부 상태를 확인할 수 없습니다");
    fillStudy();
    expect(screen.getByRole("button", { name: "연구 시작하기" })).toBeDisabled();
  });
  it("recommends public repository candidates while logged out and preserves inspection limits", async () => {
    const { api, request } = fixture({
      connection: { status: "logged_out", model_available: false },
    });
    render(<App api={api} />);
    await screen.findByRole("button", { name: "Codex 연결하기" });
    fireEvent.change(screen.getByLabelText("GitHub 사용자 이름"), { target: { value: "owner" } });
    await userEvent.click(screen.getByRole("button", { name: "연구할 저장소 추천 받기" }));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith("POST", "/api/agent/repositories", {
        owner: "owner",
        count: 3,
      }),
    );
    expect(await screen.findByText("확인한 공개 저장소: 8개")).toBeInTheDocument();
    expect(screen.getByText("Only public repositories were inspected.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "이 저장소 선택" }));
    expect(screen.getByLabelText("GitHub 저장소")).toHaveValue("https://github.com/owner/repo");
    expect(request.mock.calls.some(([, path]) => path.startsWith("/api/agent/connection/"))).toBe(
      false,
    );
  });
  it("keeps logout incomplete when backend reports a cleanup race", async () => {
    const { api, request } = fixture();
    const original = api.request;
    api.request = ((method: "GET" | "POST", path: string, body?: Record<string, unknown>) =>
      path.endsWith("/logout")
        ? Promise.reject(new Error("RESEARCH_BUSY"))
        : original(method, path, body)) as DesktopBridge["request"];
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    const dialog = await screen.findByRole("dialog", { name: "Codex에서 로그아웃할까요?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "로그아웃" }));
    await waitFor(() =>
      expect(screen.getByText(/진행 중인 연구를 중지하고 종료를 확인/)).toBeInTheDocument(),
    );
    expect(screen.getByRole("dialog", { name: "Codex에서 로그아웃할까요?" })).toBeInTheDocument();
    expect(screen.queryByText("로그아웃했습니다")).not.toBeInTheDocument();
    expect(request).not.toHaveBeenCalledWith("POST", "/api/agent/connection/disconnect", {});
  });
  it("prevents two submissions before an in-flight start request completes", async () => {
    const { api, request } = fixture();
    let complete: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      complete = resolve;
    });
    const original = api.request;
    const starts = vi.fn(async () => {
      await gate;
      return {};
    });
    api.request = ((method: "GET" | "POST", path: string, body?: Record<string, unknown>) =>
      method === "POST" && path === "/api/projects"
        ? starts()
        : original(method, path, body)) as DesktopBridge["request"];
    render(<App api={api} />);
    await ready();
    fillStudy();
    const submit = screen.getByRole("button", { name: "연구 시작하기" });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(starts).toHaveBeenCalledTimes(1);
    expect(submit).toBeDisabled();
    complete?.();
    await screen.findByText("연구를 요청했습니다");
    expect(request.mock.calls.filter(([method]) => method === "POST")).toHaveLength(0);
  });
  it("does not report success when a save dialog is canceled", async () => {
    const { api } = fixture({
      projects: [
        project(
          run({
            status: "completed",
            files: [{ name: "paper.pdf", url: "/api/projects/web-a/files/paper.pdf" }],
          }),
        ),
      ],
    });
    vi.mocked(api.saveArtifact).mockResolvedValue({ canceled: true });
    render(<App api={api} />);
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "논문 보관함" }));
    await userEvent.click(screen.getByRole("button", { name: "논문 PDF 저장" }));
    await waitFor(() => expect(api.saveArtifact).toHaveBeenCalled());
    expect(screen.queryByText("파일을 저장했습니다")).not.toBeInTheDocument();
  });
  it("does not trust an earlier verified connection when the current provider is unavailable", async () => {
    const { api, request } = fixture({ providerReady: false });
    render(<App api={api} />);
    await screen.findByText(/현재 모델 실행 연결이 준비되지 않았습니다/);
    fillStudy();
    expect(screen.queryByText("사용 준비 완료")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "연구 시작하기" })).toBeDisabled();
    expect(request.mock.calls.every(([method]) => method === "GET")).toBe(true);
  });
  it("honors the app-login-required marker even with stale positive readiness fields", async () => {
    const { api } = fixture({
      connection: {
        status: "available",
        model_available: true,
        connected: true,
        app_login_required: true,
      },
    });
    render(<App api={api} />);
    await screen.findByText(/다시 연결하면 연구를 이어갈 수 있습니다/);
    fillStudy();
    expect(screen.getByRole("button", { name: "연구 시작하기" })).toBeDisabled();
  });
  it("retains a failed logout retry after closing the dialog or loading the retained pending state", async () => {
    const { api, request } = fixture({
      connection: {
        status: "blocked",
        authentication: "unknown",
        model_available: false,
        connected: false,
        app_login_required: true,
        code: "LOGOUT_FAILED",
        pending: {
          profile_id: "11111111111111111111111111111111",
          status: "blocked",
          expires_at: null,
        },
      },
    });
    render(<App api={api} />);
    await screen.findByText(/로그아웃을 완료하지 못했습니다. 앱 전용 로그인에서/);
    fillStudy();
    expect(screen.getByRole("button", { name: "연구 시작하기" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "연결 확인 (1회 호출)" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "로그아웃 다시 시도" }));
    const firstDialog = await screen.findByRole("dialog", { name: "Codex에서 로그아웃할까요?" });
    await userEvent.click(within(firstDialog).getByRole("button", { name: "돌아가기" }));
    await userEvent.click(screen.getByRole("button", { name: "로그아웃 다시 시도" }));
    const retryDialog = await screen.findByRole("dialog", { name: "Codex에서 로그아웃할까요?" });
    await userEvent.click(within(retryDialog).getByRole("button", { name: "로그아웃" }));
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith("POST", "/api/agent/connection/logout", {}),
    );
    expect(await screen.findByText("로그아웃했습니다")).toBeInTheDocument();
    expect(
      request.mock.calls.some(
        ([, path]) =>
          path === "/api/agent/connection/login" || path === "/api/agent/connection/probe",
      ),
    ).toBe(false);
  });
  it("does not enable a probe from stale authentication without an app pending profile", async () => {
    const { api, request } = fixture({
      connection: {
        status: "authenticated",
        authentication: "chatgpt",
        model_available: false,
        connected: false,
        app_login_required: true,
        pending: null,
      },
    });
    render(<App api={api} />);
    await screen.findByText(/공식 로그인이 완료됐습니다/);
    expect(screen.queryByRole("button", { name: "연결 확인 (1회 호출)" })).not.toBeInTheDocument();
    expect(request.mock.calls.every(([method]) => method === "GET")).toBe(true);
  });
});
