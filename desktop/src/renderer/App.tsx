import { useEffect, useState } from "react";
import { Check, ChevronRight, ExternalLink, Files, FlaskConical, LoaderCircle, Plug, RefreshCw } from "lucide-react";
import type { AppSnapshot } from "../shared/contracts";
import { ResearchPane } from "./ResearchPane";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Checkbox } from "./components/ui/checkbox";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./components/ui/select";

const busyLabels = {
  "sign-in": "브라우저에서 ChatGPT 로그인을 완료해 주세요.",
  "select-profile": "선택한 ChatGPT 계정으로 전환하고 있습니다.",
  disconnect: "이 계정의 연결을 해제하고 있습니다.",
  models: "이 계정에서 사용할 수 있는 모델을 조회하고 있습니다.",
  verify: "선택한 모델의 실제 응답을 기다리고 있습니다.",
};

function accountLabel(profile: AppSnapshot["profiles"][number]) {
  const label = profile.email ? `${profile.label} · ${profile.email}` : profile.label;
  return profile.pending ? `${label} (연결 완료 필요)` : label;
}

const workspaceTabs = [
  { id: "connection", label: "연결", description: "계정 · 모델 · 크레딧", icon: Plug },
  { id: "research", label: "새 연구", description: "저장소 · 목표 · 실행", icon: FlaskConical },
  { id: "results", label: "결과", description: "작업 상태 · 결과 파일", icon: Files },
] as const;
type WorkspaceView = typeof workspaceTabs[number]["id"];

export function App() {
  const [snapshot, setSnapshot] = useState<AppSnapshot | null>(null);
  const [model, setModel] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [creditUseConfirmed, setCreditUseConfirmed] = useState(false);
  const [researchBusy, setResearchBusy] = useState(false);
  const [view, setView] = useState<WorkspaceView>("connection");

  useEffect(() => {
    let mounted = true;
    if (!window.paperFactory) {
      setLocalError("앱의 연결 모듈을 불러오지 못했습니다. Paper Factory를 다시 실행해 주세요.");
      return;
    }
    const unsubscribe = window.paperFactory.onSnapshot((next) => {
      if (mounted) setSnapshot(next);
    });
    window.paperFactory.snapshot().then(
      (next) => {
        if (mounted) setSnapshot(next);
      },
      () => {
        if (mounted) setLocalError("로컬 연결 상태를 읽지 못했습니다. Paper Factory를 다시 실행해 주세요.");
      },
    );
    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!snapshot) return;
    setModel((current) =>
      snapshot.models.some((item) => item.slug === current)
        ? current
        : (snapshot.models[0]?.slug ?? ""),
    );
  }, [snapshot?.models, snapshot?.session.profileId]);

  useEffect(() => {
    setCreditUseConfirmed(false);
  }, [snapshot?.session.profileId]);

  async function runAction(name: string, operation: () => Promise<AppSnapshot | void>) {
    setPending(name);
    setLocalError(null);
    if (["verify", "profile", "sign-in", "add-account", "disconnect"].includes(name)) {
      setCreditUseConfirmed(false);
    }
    try {
      const next = await operation();
      if (next) setSnapshot(next);
    } catch {
      setLocalError("앱과 통신하지 못했습니다. 다시 시도하거나 Paper Factory를 다시 실행해 주세요.");
    } finally {
      setPending(null);
    }
  }

  const busy = snapshot?.busy ?? null;
  const connectionBusy = busy !== null || pending !== null;
  const locked = connectionBusy || researchBusy;
  const connected = snapshot?.session.connected ?? false;
  const sharing = snapshot?.session.sharing ?? false;
  const verification = snapshot?.verification;
  const error = localError ?? snapshot?.error?.message;
  const account = snapshot?.session.account;
  const usageLimitReached = snapshot?.error?.code === "subscription_sharing_usage_limit_exceeded";

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <h1>Paper Factory</h1>
        <span className="topbar-divider" aria-hidden="true" />
        <span className="topbar-location">{workspaceTabs.find((tab) => tab.id === view)?.label}</span>
        <div className="topbar-status">
          <span className="topbar-account">{connected ? "ChatGPT 연결됨" : "ChatGPT 연결 필요"}</span>
          <Badge variant="neutral">{snapshot ? `v${snapshot.version}` : "연결 준비"}</Badge>
        </div>
      </header>

      <aside className="workspace-sidebar" aria-label="작업 공간 탐색">
        <div className="sidebar-heading"><span className="sidebar-mark" aria-hidden="true">PF</span><span>작업 공간</span></div>
        <div className="workspace-tabs" role="tablist" aria-label="작업 화면" aria-orientation="vertical">
          {workspaceTabs.map((tab, index) => (
            <Button key={tab.id} role="tab" id={`workspace-tab-${tab.id}`} aria-label={tab.label}
              aria-controls={`${tab.id}-panel`} aria-selected={view === tab.id} tabIndex={view === tab.id ? 0 : -1}
              variant={view === tab.id ? "default" : "ghost"} className="workspace-tab"
              onClick={() => setView(tab.id)} onKeyDown={(event) => {
                const nextIndex = event.key === "ArrowDown" ? (index + 1) % workspaceTabs.length
                  : event.key === "ArrowUp" ? (index + workspaceTabs.length - 1) % workspaceTabs.length
                    : event.key === "Home" ? 0 : event.key === "End" ? workspaceTabs.length - 1 : null;
                if (nextIndex === null) return;
                event.preventDefault();
                const next = workspaceTabs[nextIndex]!;
                setView(next.id);
                document.getElementById(`workspace-tab-${next.id}`)?.focus();
              }}>
              <tab.icon aria-hidden="true" />
              <span className="sidebar-tab-copy"><span>{tab.label}</span><span className="sidebar-tab-description">{tab.description}</span></span>
            </Button>
          ))}
        </div>
        <div className="sidebar-note">
          <span className={`connection-indicator ${connected && sharing ? "is-connected" : ""}`} aria-hidden="true" />
          <span>{researchBusy ? "연구 작업 진행 중" : connected && sharing ? "연구를 시작할 수 있습니다" : "연결 화면에서 시작하세요"}</span>
        </div>
      </aside>

      <main className="workspace-main">
      <section id="connection-panel" role="tabpanel" aria-labelledby="workspace-tab-connection"
        hidden={view !== "connection"} className="workspace-panel" tabIndex={0}>
      <Card className="connection-card workspace-card">
        <CardHeader>
          <div className="section-heading">
            <CardTitle role="heading" aria-level={2} className="text-xl">ChatGPT 연결</CardTitle>
            <Badge variant={connected ? "default" : "neutral"}>
              {connected ? "로그인 완료" : "연결 안 됨"}
            </Badge>
          </div>
          <CardDescription>
            ChatGPT 계정으로 로그인한 뒤 실제 모델 응답을 확인합니다.
            계정 로그인과 모델 사용 확인은 각각 표시됩니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {!snapshot && !error && (
            <p className="progress-message" role="status">
              <LoaderCircle className="status-spinner" aria-hidden="true" />
              저장된 연결 상태를 불러오고 있습니다.
            </p>
          )}

          {snapshot && (
            <>
              {snapshot.profiles.length > 0 && (
                <div className="field">
                  <label id="profile-label">ChatGPT 계정</label>
                  <Select
                    value={snapshot.session.profileId ?? null}
                    items={snapshot.profiles.map((profile) => ({
                      value: profile.id,
                      label: accountLabel(profile),
                    }))}
                    onValueChange={(id) => {
                      if (id && id !== snapshot.session.profileId) {
                        const profile = snapshot.profiles.find((item) => item.id === id);
                        if (profile?.pending) {
                          void runAction("sign-in", () => window.paperFactory.signIn(id));
                        } else {
                          void runAction("profile", () => window.paperFactory.selectProfile(id));
                        }
                      }
                    }}
                    disabled={locked}
                  >
                    <SelectTrigger aria-labelledby="profile-label">
                      <SelectValue placeholder="계정 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {snapshot.profiles.map((profile) => (
                        <SelectItem key={profile.id} value={profile.id}>
                          {accountLabel(profile)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {connected && (
                <div className="connection-detail">
                  <p>{account?.email ?? account?.name ?? "ChatGPT 계정에 연결되었습니다."}</p>
                  <p className="detail-note">
                    {sharing
                      ? "Paper Factory에 모델 사용 권한이 연결되었습니다."
                      : "모델 사용 권한 연결을 확인해 주세요."}
                  </p>
                </div>
              )}

              <div className="action-row">
                <Button
                  disabled={locked}
                  onClick={() => void runAction("sign-in", () =>
                    window.paperFactory.signIn(snapshot.session.profileId))}
                >
                  Continue with ChatGPT
                </Button>
                {snapshot.profiles.length > 0 && (
                  <Button
                    variant="neutral"
                    disabled={locked}
                    onClick={() => void runAction("add-account", () => window.paperFactory.signIn())}
                  >
                    계정 추가
                  </Button>
                )}
                {connected && (
                  <Button
                    variant="outline"
                    disabled={locked}
                    onClick={() => void runAction("disconnect", () => window.paperFactory.disconnect())}
                  >
                    연결 해제
                  </Button>
                )}
              </div>

              <div className="verification-section">
                <div className="section-heading">
                  <h2>모델 사용 확인</h2>
                  <Badge variant={verification ? "default" : "neutral"}>
                    {verification ? "실제 응답 확인" : "미확인"}
                  </Badge>
                </div>
                <p className="detail-note">
                  짧은 고정 확인 요청을 보내 응답을 끝까지 받습니다.
                  ChatGPT 구독의 사용량 제한이 적용됩니다.
                </p>
                {sharing && <p className="detail-note">Using ChatGPT plan · 구독 한도와 크레딧 사용 설정 적용</p>}
                <div className="field">
                  <label id="model-label">이 계정에서 사용할 수 있는 모델</label>
                  <Select
                    value={model || null}
                    items={snapshot.models.map((item) => ({ value: item.slug, label: item.displayName }))}
                    onValueChange={(slug) => setModel(slug ?? "")}
                    disabled={!connected || !sharing || locked || snapshot.models.length === 0}
                  >
                    <SelectTrigger aria-labelledby="model-label">
                      <SelectValue placeholder={connected ? "모델 조회 필요" : "먼저 ChatGPT에 로그인하세요"} />
                    </SelectTrigger>
                    <SelectContent>
                      {snapshot.models.map((item) => (
                        <SelectItem key={item.slug} value={item.slug}>{item.displayName}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="action-row">
                  <Button
                    disabled={!connected || !sharing || !model || locked || (usageLimitReached && !creditUseConfirmed)}
                    onClick={() => void runAction("verify", () => window.paperFactory.verify(model))}
                  >
                    실제 응답 확인
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!connected || !sharing || locked}
                    onClick={() => void runAction("models", () => window.paperFactory.refreshModels())}
                  >
                    <RefreshCw aria-hidden="true" /> 모델 새로고침
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={locked}
                    onClick={() => void runAction("usage", () => window.paperFactory.openUsage())}
                  >
                    사용량 확인 <ExternalLink aria-hidden="true" />
                  </Button>
                </div>
                <section className="space-y-3 rounded-base border-2 border-border bg-secondary-background p-4"
                  aria-labelledby="credit-settings-label">
                  <h3 id="credit-settings-label" className="font-semibold">ChatGPT 크레딧 사용</h3>
                  <p className="detail-note">
                    구독 사용량 한도에 도달한 뒤에도 보유한 ChatGPT 크레딧을 사용하려면,
                    ChatGPT 사용량 페이지에서 다음 옵션을 켜 주세요.
                  </p>
                  <p className="detail-note">사용량 한도에 도달한 후 다른 앱에서 크레딧 사용 허용</p>
                  <Button variant="outline" disabled={locked}
                    onClick={() => void runAction("usage", () => window.paperFactory.openUsage())}>
                    크레딧 사용 설정 <ExternalLink aria-hidden="true" />
                  </Button>
                </section>
              </div>
            </>
          )}

          {busy && (
            <div className="progress-panel" role="status">
              <p className="progress-message">
                <LoaderCircle className="status-spinner" aria-hidden="true" />
                {busyLabels[busy]}
              </p>
              {(busy === "sign-in" || busy === "models" || busy === "verify") && (
                <Button
                  variant="neutral"
                  onClick={() => void runAction("cancel", () => window.paperFactory.cancel())}
                >
                  취소
                </Button>
              )}
            </div>
          )}

          {error && (
            <div className="error-panel" role="alert">
              <p>{error}</p>
              {!localError && snapshot?.error && (
                <p className="detail-note">오류 코드: {snapshot.error.code}</p>
              )}
              {!localError && usageLimitReached && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Checkbox id="credit-use-confirmed" checked={creditUseConfirmed}
                      onCheckedChange={(checked) => setCreditUseConfirmed(checked)} disabled={locked} />
                    <label htmlFor="credit-use-confirmed" className="detail-note">
                      ChatGPT에서 크레딧 사용 허용을 켰습니다
                    </label>
                  </div>
                  <p className="detail-note">
                    이 체크는 재시도를 위한 사용자 확인이며 ChatGPT 계정 설정을 변경하지 않습니다.
                    설정을 켠 뒤 체크하고 실제 응답 확인 버튼을 눌러 주세요.
                  </p>
                </div>
              )}
              {snapshot?.error?.action === "usage" && (
                <Button variant="outline" disabled={locked}
                  onClick={() => void runAction("usage", () => window.paperFactory.openUsage())}>
                  ChatGPT 사용량 확인 <ExternalLink aria-hidden="true" />
                </Button>
              )}
              {snapshot?.error?.action === "sign-in" && (
                <p className="detail-note">Continue with ChatGPT 버튼으로 다시 연결해 주세요.</p>
              )}
              {snapshot?.error?.action === "retry" && (
                <p className="detail-note">연결 상태를 확인한 뒤 실패한 작업을 다시 시도해 주세요.</p>
              )}
            </div>
          )}

          {verification && (
            <section className="response-panel" aria-labelledby="response-label">
              <h2 id="response-label" className="response-heading">
                <Check aria-hidden="true" /> 실제 모델 응답
              </h2>
              <p className="response-text">{verification.text}</p>
              <p className="detail-note">
                {verification.model} · {new Date(verification.completedAt).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}
              </p>
            </section>
          )}
          {connected && sharing && (
            <div className="next-step-panel">
              <div><strong>연구할 준비를 이어가세요.</strong><p className="detail-note">새 연구에서 저장소·목표·작성 및 리뷰 모델을 선택합니다.</p></div>
              <Button variant="neutral" onClick={() => setView("research")}>새 연구로 이동 <ChevronRight aria-hidden="true" /></Button>
            </div>
          )}
        </CardContent>
      </Card>
      </section>

      {snapshot && <ResearchPane connection={snapshot} connectionBusy={connectionBusy} onBusyChange={setResearchBusy}
        view={view} onNavigate={setView} />}
      {!snapshot && view !== "connection" && (
        <section id={`${view}-panel`} role="tabpanel" aria-labelledby={`workspace-tab-${view}`} className="workspace-panel">
          <Card className="workspace-card"><CardHeader><CardTitle>연결 상태 준비</CardTitle>
            <CardDescription>연결 상태를 불러온 뒤 연구 작업과 결과를 확인할 수 있습니다.</CardDescription></CardHeader>
            <CardContent><Button variant="neutral" onClick={() => setView("connection")}>연결 화면으로 이동</Button></CardContent></Card>
        </section>
      )}
      </main>

      <footer className="app-statusbar">
        <span>로컬 작업 공간 · 이 컴퓨터에 저장</span>
        <span>{researchBusy ? "연구 진행 중 · 결과에서 확인" : sharing ? "Using ChatGPT plan" : "모델 사용에는 ChatGPT 연결이 필요합니다"}</span>
      </footer>
    </div>
  );
}
