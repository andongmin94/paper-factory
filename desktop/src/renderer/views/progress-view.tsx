import { BookOpen, Check, GitBranch, Play, Square } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Progress, ProgressLabel } from "../components/ui/progress";
import { Empty, Loading } from "../components/workspace-states";
import type { Project, ResearchRun } from "../model";
import {
  activeStatus,
  interruptionMessage,
  progress,
  resumableStatus,
  shortRepository,
  stages,
  statusLabel,
} from "../model";

interface ProgressViewProps {
  projects: Project[];
  runs: ResearchRun[];
  loading: boolean;
  pending: boolean;
  canResume: boolean;
  onCancel: (target: ResearchRun) => void;
  onResume: (target: ResearchRun) => void;
  onStart: () => void;
  onLibrary: () => void;
}

export function ProgressView({
  projects,
  runs,
  loading,
  pending,
  canResume,
  onCancel,
  onResume,
  onStart,
  onLibrary,
}: ProgressViewProps) {
  return (
    <>
      <div className="page-heading compact">
        <Badge className="eyebrow">RESEARCH IN MOTION</Badge>
        <h1>
          진행 현황<span className="heading-dot">.</span>
        </h1>
        <p>완료한 단계와 사용한 한도를 확인하세요. 연구 기록은 중지 후에도 남습니다.</p>
      </div>
      {loading && <Loading />}
      {projects
        .filter(
          (project) =>
            project.status === "importing" ||
            project.status === "failed" ||
            project.autonomous_error,
        )
        .map((project) => (
          <Card key={`import-${project.id}`} className="import-card">
            <CardContent>
              <div className="row">
                <GitBranch />
                <strong>{project.name}</strong>
                <Badge variant="neutral">{statusLabel(project.status)}</Badge>
              </div>
              <p>
                {project.status === "importing"
                  ? "저장소를 가져오고 있습니다. 준비되면 요청한 연구를 자동으로 시작합니다."
                  : project.autonomous_error
                    ? "저장소는 준비됐지만 연구를 시작하지 못했습니다. 연결 상태를 확인하고 자동 연구 화면에서 이 프로젝트를 선택하세요."
                    : "저장소를 가져오지 못했습니다. 주소와 접근 권한을 확인한 뒤 새로 가져와 주세요."}
              </p>
            </CardContent>
          </Card>
        ))}
      {!loading &&
        runs.length === 0 &&
        projects.every((project) => project.status !== "importing") && (
          <Empty
            icon="progress"
            title="아직 시작한 연구가 없습니다"
            description="GitHub 저장소와 연구 목표를 입력해 첫 연구를 시작하세요."
            onStart={onStart}
          />
        )}
      <div className="run-list">
        {runs.map(({ project, run }) => {
          const completion = progress(run);
          const current =
            stages.find(([key]) => key === run.stage)?.[1] ??
            (run.stage === "done" ? "최종 확인 완료" : "작업 준비");
          return (
            <Card key={run.id} className="run-card">
              <CardHeader>
                <div className="run-topline">
                  <span className="repo-label">
                    <GitBranch size={16} />
                    {shortRepository(project.source)}
                  </span>
                  <Badge
                    className={run.status === "completed" ? "ready-badge" : ""}
                    variant="neutral"
                  >
                    {run.cancellation_requested && activeStatus(run.status)
                      ? "중지 요청 · 정리 중"
                      : statusLabel(run.status)}
                  </Badge>
                </div>
                <CardTitle className="run-goal">{run.goal}</CardTitle>
              </CardHeader>
              <CardContent>
                <Progress value={completion.percent}>
                  <ProgressLabel>
                    완료한 단계 {completion.completed} / {stages.length}
                  </ProgressLabel>
                  <span className="progress-current">{current}</span>
                </Progress>
                <ol className="stage-list">
                  {stages.map(([key, label], index) => (
                    <li
                      key={key}
                      className={
                        completion.finished.has(key)
                          ? "done"
                          : run.stage === key && activeStatus(run.status)
                            ? "current"
                            : ""
                      }
                    >
                      <span>{completion.finished.has(key) ? <Check size={12} /> : index + 1}</span>
                      {label}
                    </li>
                  ))}
                </ol>
                <div className="run-footer">
                  <div className="run-budget">
                    <span>
                      모델 호출{" "}
                      <strong>
                        {run.model_calls ?? 0} / {run.budget?.max_model_calls ?? "—"}회
                      </strong>
                    </span>
                    <span>
                      사용 시간{" "}
                      <strong>
                        {Math.floor((run.elapsed_seconds ?? 0) / 60)} /{" "}
                        {run.budget?.wall_seconds ? Math.floor(run.budget.wall_seconds / 60) : "—"}
                        분
                      </strong>
                    </span>
                  </div>
                  <div className="run-actions">
                    {activeStatus(run.status) && (
                      <Button
                        variant="neutral"
                        size="sm"
                        disabled={Boolean(pending) || run.cancellation_requested}
                        onClick={() => onCancel({ project, run })}
                      >
                        <Square size={13} />
                        {run.cancellation_requested ? "종료 확인 중" : "연구 중지"}
                      </Button>
                    )}
                    {resumableStatus(run.status) && (
                      <Button
                        size="sm"
                        disabled={!canResume}
                        onClick={() => onResume({ project, run })}
                      >
                        <Play size={13} />
                        이어서 진행
                      </Button>
                    )}
                    {run.status === "completed" && (
                      <Button size="sm" onClick={onLibrary}>
                        <BookOpen size={14} />
                        결과 확인
                      </Button>
                    )}
                  </div>
                </div>
                {resumableStatus(run.status) && (
                  <div className="run-warning">
                    <p>{interruptionMessage(run)}</p>
                    {run.code && <span>상태 코드: {run.code}</span>}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}
