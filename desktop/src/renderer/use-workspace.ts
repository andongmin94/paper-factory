import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AgentStatus,
  Connection,
  DesktopBridge,
  Job,
  Project,
  Snapshot,
  Study,
} from "./model";
import { initialSnapshot } from "./model";

export function useWorkspace(api: DesktopBridge) {
  const [snapshot, setSnapshot] = useState<Snapshot>(initialSnapshot);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [version, setVersion] = useState("");
  const inFlight = useRef(false);
  const currentRefresh = useRef<Promise<void> | null>(null);
  const mounted = useRef(false);

  const fetchSnapshot = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const result = await Promise.allSettled([
        api.getRuntimeInfo(),
        api.request<AgentStatus>("GET", "/api/agent/status"),
        api.request<Connection>("GET", "/api/agent/connection"),
        api.request<{ projects: Project[] }>("GET", "/api/projects"),
        api.request<{ jobs: Job[] }>("GET", "/api/jobs"),
        api.request<{ studies: Study[] }>("GET", "/api/studies"),
      ]);
      if (!mounted.current) return;
      const errors = result.filter((entry) => entry.status === "rejected");
      setLoadError(
        errors.length ? "작업실에 연결하지 못한 항목이 있습니다. 잠시 후 다시 확인해 주세요." : "",
      );
      if (result[0].status === "fulfilled") setVersion(result[0].value.version);
      let projects: Project[] | undefined;
      if (result[3].status === "fulfilled") {
        const listed = result[3].value.projects;
        const details = await Promise.allSettled(
          listed.map((project) =>
            api.request<Project>("GET", `/api/projects/${encodeURIComponent(project.id)}`),
          ),
        );
        projects = listed.map((project, index) =>
          details[index].status === "fulfilled" ? details[index].value : project,
        );
        if (details.some((entry) => entry.status === "rejected"))
          setLoadError(
            "일부 연구 기록을 불러오지 못했습니다. 새로고침하면 다시 확인할 수 있습니다.",
          );
      }
      if (!mounted.current) return;
      setSnapshot((previous) => ({
        agent: result[1].status === "fulfilled" ? result[1].value : {},
        connection: result[2].status === "fulfilled" ? result[2].value : { status: "unavailable" },
        projects: projects ?? previous.projects,
        jobs: result[4].status === "fulfilled" ? result[4].value.jobs : previous.jobs,
        studies: result[5].status === "fulfilled" ? result[5].value.studies : previous.studies,
      }));
    } catch {
      if (mounted.current)
        setLoadError("연구 작업실을 준비하지 못했습니다. 앱을 다시 열거나 새로고침해 주세요.");
    } finally {
      inFlight.current = false;
      if (mounted.current) setLoading(false);
    }
  }, [api]);

  const refresh = useCallback(
    async (fresh = false) => {
      if (currentRefresh.current) {
        await currentRefresh.current;
        if (!fresh) return;
      }
      const request = fetchSnapshot();
      currentRefresh.current = request;
      try {
        await request;
      } finally {
        if (currentRefresh.current === request) currentRefresh.current = null;
      }
    },
    [fetchSnapshot],
  );

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 4000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [refresh]);

  return { snapshot, loading, loadError, version, refresh };
}
