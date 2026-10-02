import { describe, expect, it } from "vitest";
import { artifactRequestPath, connectionMessage, progress, validRepository } from "./model";

describe("research status and bounded artifact paths", () => {
  it("counts only the latest completed stage attempt", () => {
    const result = progress({
      id: "run",
      goal: "goal",
      stage: "execute",
      status: "blocked",
      attempts: [
        { stage: "assess", status: "completed" },
        { stage: "execute", status: "completed" },
        { stage: "execute", status: "failed" },
        { stage: "unknown", status: "completed" },
      ],
    });
    expect(result.completed).toBe(1);
    expect(result.finished.has("execute")).toBe(false);
    expect(result.percent).toBe(11);
  });
  it("does not invent progress from a running stage or completion status", () => {
    expect(progress({ id: "run", goal: "goal", stage: "done", status: "completed" }).percent).toBe(
      0,
    );
  });
  it.each([
    "/api/projects/web-a/files/autonomous/paper.pdf",
    "/api/studies/example/bundle",
    "/api/studies/example/files/my%20paper.docx",
  ])("allows declared relative artifact endpoint %s", (url) => {
    expect(artifactRequestPath({ url })).toBe(url);
  });
  it.each([
    "https://example.com/paper.pdf",
    "/api/agent/status",
    "/api/projects/a/files/../../auth.json",
    "/api/projects/a/files/%2E%2E/auth.json",
    "/api/projects/a/files/%2fsecret",
    "/api/projects/a/files/a%5csecret",
    "/api/projects/a/files/a?token=secret",
    "/api/projects/a/files/a%00.pdf",
    "/api/projects/a/files/%ZZ",
  ])("rejects out of scope or ambiguous artifact URL %s", (url) => {
    expect(artifactRequestPath({ url })).toBeNull();
  });
  it("accepts only HTTPS GitHub repository URLs", () => {
    expect(validRepository("https://github.com/owner/repo")).toBe(true);
    expect(validRepository("https://github.com.evil.test/owner/repo")).toBe(false);
    expect(validRepository("C:/private/project")).toBe(false);
    expect(validRepository("http://github.com/owner/repo")).toBe(false);
  });
  it("keeps explicit logout and authenticated-but-unprobed states clear", () => {
    expect(connectionMessage({ status: "logged_out" }, { provider: { ready: true } })).toContain(
      "다시 연결",
    );
    expect(connectionMessage({ status: "authenticated" }, {})).toContain("연결 확인");
  });
  it.each([
    ["waiting_user", "공식 로그인 페이지"],
    ["authenticated", "연결 확인"],
    ["probing", "연결을 확인"],
  ])("prioritizes the %s connection phase over an app-login-required marker", (status, message) => {
    expect(
      connectionMessage({ status, app_login_required: true }, { provider: { ready: false } }),
    ).toContain(message);
  });
});
