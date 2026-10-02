// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  artifactName,
  isTrustedFrame,
  MAX_JSON,
  parseBackendReady,
  validateApiRequest,
  validateArtifactPath,
  validateDeviceUrl,
} from "./security.js";

describe("desktop IPC boundary", () => {
  it("permits the app's documented operations and finite JSON", () => {
    expect(
      validateApiRequest("POST", "/api/projects/example/pipelines", {
        goal: "분석",
        budget: { max_model_calls: 16 },
      }).body,
    ).toContain("분석");
    expect(validateApiRequest("POST", "/api/agent/connection/logout").body).toBe("{}");
    expect(validateApiRequest("GET", "/api/projects/example/pipelines/pipe-1").path).toBe(
      "/api/projects/example/pipelines/pipe-1",
    );
  });
  it.each([
    ["POST", "/api/desktop/shutdown"],
    ["POST", "/api/agent/connection/disconnect"],
    ["PUT", "/api/projects/x/manuscripts/y/canonical"],
    ["GET", "https://example.com/api/health"],
    ["GET", "//example.com/api/health"],
    ["GET", "/api/health?url=https://example.com"],
    ["GET", "/api/projects/%2e%2e"],
    ["GET", "/api/projects/x%2fy"],
    ["GET", "/api/projects/x\\files\\secret"],
    ["GET", "/api/projects/x/files/private.json"],
  ])("rejects unexposed method/path %s %s", (method, route) => {
    expect(() => validateApiRequest(method, route)).toThrow();
  });
  it("rejects oversized and nonfinite payloads", () => {
    expect(() =>
      validateApiRequest("POST", "/api/projects", { source: "x".repeat(MAX_JSON) }),
    ).toThrow();
    expect(() =>
      validateApiRequest("POST", "/api/projects", { budget: { wall_seconds: NaN } }),
    ).toThrow();
    expect(() => validateApiRequest("GET", "/api/health", {})).toThrow();
  });
  it("limits artifact access to declared API file routes", () => {
    expect(artifactName("/api/projects/x/files/papers/%ED%95%9C%EA%B8%80.pdf")).toBe("한글.pdf");
    expect(validateArtifactPath("/api/studies/x/bundle")).toBe("/api/studies/x/bundle");
    for (const route of [
      "file:///C:/secret.pdf",
      "/api/projects/x/files/%2e%2e/secret.pdf",
      "/api/projects/x/files/a%2fb.pdf",
      "/api/projects/x/files/evil.exe",
      "/api/projects/x/files/C%3A/secret.pdf",
    ])
      expect(() => validateArtifactPath(route)).toThrow();
  });
  it("accepts only the exact official device URL", () => {
    expect(validateDeviceUrl("https://auth.openai.com/codex/device")).toContain("auth.openai.com");
    for (const url of [
      "https://auth.openai.com.evil.test/codex/device",
      "https://auth.openai.com/codex/device?redirect=evil",
      "file:///C:/cmd.exe",
      "https://auth.openai.com/codex/device#x",
    ])
      expect(() => validateDeviceUrl(url)).toThrow();
  });
  it("keeps readiness on one explicit loopback origin", () => {
    const token = "a".repeat(43);
    expect(parseBackendReady({ url: "http://127.0.0.1:12345", token }).url).toBe(
      "http://127.0.0.1:12345",
    );
    for (const url of [
      "https://127.0.0.1:12345",
      "http://localhost:12345",
      "http://evil.test:12345",
      "http://127.0.0.1:12345/api",
      "http://user:password@127.0.0.1:12345",
    ])
      expect(() => parseBackendReady({ url, token })).toThrow();
    expect(() => parseBackendReady({ url: "http://127.0.0.1:12345", token: "short" })).toThrow();
  });
  it("rejects subframes, other windows and navigated senders", () => {
    const url = "paperfactory://app/";
    expect(isTrustedFrame(1, 1, true, url, url)).toBe(true);
    expect(isTrustedFrame(1, 1, false, url, url)).toBe(false);
    expect(isTrustedFrame(2, 1, true, url, url)).toBe(false);
    expect(isTrustedFrame(1, 1, true, "https://evil.test/", url)).toBe(false);
    expect(isTrustedFrame(1, 1, true, "paperfactory://app/other.html", url)).toBe(false);
  });
});
