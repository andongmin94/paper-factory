import { ExternalLink, LogOut } from "lucide-react";
import { CODEX_DEVICE_URL } from "@shared/api";
import type { AgentStatus, Connection } from "../model";
import { connectionMessage, connectionReadiness } from "../model";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface ConnectionCardProps {
  connection: Connection;
  agent: AgentStatus;
  loading: boolean;
  pending: boolean;
  researchBusy: boolean;
  onConnect: (operation: "login" | "probe" | "cancel") => void;
  onDevicePage: () => void;
  onLogout: () => void;
}

export function ConnectionCard({
  connection,
  agent,
  loading,
  pending,
  researchBusy,
  onConnect,
  onDevicePage,
  onLogout,
}: ConnectionCardProps) {
  const { authBusy, modelReady, canProbe, canLogout, logoutRetry } = connectionReadiness(
    connection,
    agent,
  );
  return (
    <Card className="account-card">
      <CardHeader>
        <CardTitle className="section-title">
          <span className="number-chip">✓</span>Codex 연결
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Badge variant="neutral" className={modelReady ? "ready-badge" : ""}>
          {modelReady ? "사용 준비 완료" : authBusy ? "연결 진행 중" : "연결 필요"}
        </Badge>
        <p className="account-description">{connectionMessage(connection, agent)}</p>
        {connection.status === "waiting_user" && (
          <div className="device-box">
            <span>일회용 로그인 코드</span>
            <strong>
              {connection.user_code && /^[A-Za-z0-9-]{1,32}$/.test(connection.user_code)
                ? connection.user_code
                : "코드 준비 중"}
            </strong>
            <Button
              className="full-width"
              disabled={Boolean(pending) || connection.verification_url !== CODEX_DEVICE_URL}
              onClick={onDevicePage}
            >
              공식 로그인 페이지 열기
              <ExternalLink size={15} />
            </Button>
            <p>OpenAI 페이지에서만 로그인 정보를 입력하세요.</p>
          </div>
        )}
        {canProbe && (
          <p className="field-help">
            연결 확인은 실제 모델을 1회 호출하며 구독 사용량에 반영됩니다.
          </p>
        )}
        <div className="account-actions">
          {canProbe ? (
            <Button
              variant="neutral"
              disabled={Boolean(pending) || researchBusy}
              onClick={() => onConnect("probe")}
            >
              {modelReady ? "연결 다시 확인 (1회 호출)" : "연결 확인 (1회 호출)"}
            </Button>
          ) : (
            !authBusy && (
              <Button
                className="full-width"
                disabled={Boolean(pending) || loading || researchBusy}
                onClick={() => onConnect("login")}
              >
                <ExternalLink size={16} />
                Codex 연결하기
              </Button>
            )
          )}
          {authBusy && connection.status !== "logging_out" && (
            <Button
              variant="neutral"
              disabled={Boolean(pending)}
              onClick={() => onConnect("cancel")}
            >
              연결 취소
            </Button>
          )}
          {canLogout && (
            <Button
              variant="ghost"
              className="logout-button"
              disabled={Boolean(pending) || authBusy}
              onClick={onLogout}
            >
              <LogOut size={15} />
              {logoutRetry ? "로그아웃 다시 시도" : "로그아웃"}
            </Button>
          )}
        </div>
        {researchBusy && (
          <p className="field-help">계정 변경은 진행 중인 연구가 종료된 뒤 가능합니다.</p>
        )}
      </CardContent>
    </Card>
  );
}
