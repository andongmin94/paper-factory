import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DesktopBridge, Project } from "./model";
import { useWorkspace } from "./use-workspace";

const runtime = { version: "0.9.0", platform: "win32", backend: "ready" as const };

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function fixture() {
  const project: Project = {
    id: "web-a",
    name: "repository",
    status: "ready",
    pipelines: [{ id: "run-a", goal: "research goal", stage: "execute", status: "running" }],
  };
  const state = {
    detail: project,
    failDetail: false,
    detailPending: null as Promise<Project> | null,
  };
  const getRuntimeInfo = vi.fn(async () => runtime);
  const request = vi.fn(async (_method: string, route: string) => {
    switch (route) {
      case "/api/agent/status":
        return { provider: { ready: true } };
      case "/api/agent/connection":
        return { status: "available", model_available: true };
      case "/api/projects":
        return { projects: [{ id: project.id, name: project.name, status: project.status }] };
      case "/api/projects/web-a": {
        if (state.failDetail) throw new Error("Temporary detail failure");
        if (state.detailPending) return state.detailPending;
        return state.detail;
      }
      case "/api/jobs":
        return { jobs: [] };
      case "/api/studies":
        return { studies: [] };
      default:
        throw new Error(`Unexpected route ${route}`);
    }
  });
  const api: DesktopBridge = {
    request: request as DesktopBridge["request"],
    getRuntimeInfo,
    openExternal: vi.fn(async () => {}),
    saveArtifact: vi.fn(async () => ({ canceled: true })),
    openArtifact: vi.fn(async () => {}),
  };
  return { api, state, getRuntimeInfo };
}

describe("workspace refresh", () => {
  it("retains running pipeline records across a failed detail fetch and updates them on recovery", async () => {
    const { api, state } = fixture();
    const { result } = renderHook(() => useWorkspace(api));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.snapshot.projects[0].pipelines?.[0].status).toBe("running");

    state.failDetail = true;
    await act(async () => {
      await result.current.refresh(true);
    });
    expect(result.current.loadError).not.toBe("");
    expect(result.current.snapshot.projects[0].pipelines?.[0].status).toBe("running");

    state.failDetail = false;
    state.detail = {
      ...state.detail,
      pipelines: [{ ...state.detail.pipelines![0], status: "completed" }],
    };
    const recovery = deferred<Project>();
    state.detailPending = recovery.promise;
    const refreshing = result.current.refresh(true);
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.loadError).not.toBe("");
    await act(async () => {
      recovery.resolve(state.detail);
      await refreshing;
    });
    expect(result.current.loadError).toBe("");
    expect(result.current.snapshot.projects[0].pipelines?.[0].status).toBe("completed");
  });

  it("coalesces concurrent fresh refreshes and keeps callers waiting for the post-action snapshot", async () => {
    const { api, getRuntimeInfo } = fixture();
    const { result } = renderHook(() => useWorkspace(api));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const oldFetch = deferred<typeof runtime>();
    const freshFetch = deferred<typeof runtime>();
    getRuntimeInfo
      .mockImplementationOnce(() => oldFetch.promise)
      .mockImplementationOnce(() => freshFetch.promise);

    let secondFreshFinished = false;
    const polling = result.current.refresh();
    const firstFresh = result.current.refresh(true);
    const secondFresh = result.current.refresh(true).then(() => {
      secondFreshFinished = true;
    });
    await act(async () => {
      oldFetch.resolve(runtime);
      await polling;
    });
    expect(getRuntimeInfo).toHaveBeenCalledTimes(3);
    expect(secondFreshFinished).toBe(false);

    await act(async () => {
      freshFetch.resolve(runtime);
      await Promise.all([firstFresh, secondFresh]);
    });
    expect(secondFreshFinished).toBe(true);
    expect(getRuntimeInfo).toHaveBeenCalledTimes(3);
    expect(result.current.loadError).toBe("");
  });
});
