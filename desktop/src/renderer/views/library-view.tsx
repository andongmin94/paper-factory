import { Download, ExternalLink, GitBranch, Search } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Empty, Loading } from "../components/workspace-states";
import type { Artifact, ResearchRun, Study } from "../model";
import { artifactKind, artifactRequestPath, readableSize, shortRepository } from "../model";

type LibraryEntry = { id: string; title: string; repository: string; files: Artifact[] };
interface LibraryViewProps {
  runs: ResearchRun[];
  studies: Study[];
  loading: boolean;
  pending: boolean;
  query: string;
  onQuery: (query: string) => void;
  onFileAction: (file: Artifact, operation: "open" | "save") => void;
  onStart: () => void;
}

export function LibraryView({
  runs,
  studies,
  loading,
  pending,
  query,
  onQuery,
  onFileAction,
  onStart,
}: LibraryViewProps) {
  const library: LibraryEntry[] = [
    ...runs
      .filter(({ run }) => run.status === "completed")
      .map(({ project, run }) => ({
        id: run.id,
        title: run.goal,
        repository: shortRepository(project.source),
        files: run.files ?? [],
      })),
    ...studies.map((study) => ({
      id: `catalog-${study.slug}`,
      title: study.title_ko ?? study.title ?? study.slug,
      repository:
        typeof study.repository === "string"
          ? shortRepository(study.repository)
          : (study.repository?.name ?? "보관된 연구"),
      files: [
        ...(study.files ?? []),
        ...(study.bundle_url && !(study.files ?? []).some((file) => file.url === study.bundle_url)
          ? [{ name: "reproducibility.zip", url: study.bundle_url }]
          : []),
      ],
    })),
  ];
  const filteredLibrary = library.filter((entry) =>
    `${entry.title} ${entry.repository}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  );

  return (
    <>
      <div className="page-heading compact">
        <Badge className="eyebrow">YOUR PAPER COLLECTION</Badge>
        <h1>
          논문 보관함<span className="heading-dot">.</span>
        </h1>
        <p>검토용 원고와 실험을 확인할 재현 자료를 열거나 저장하세요.</p>
      </div>
      <div className="library-toolbar">
        <label className="library-search">
          <Search size={18} />
          <Input
            aria-label="논문 검색"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="연구 목표 또는 저장소로 검색"
          />
        </label>
        <span>{filteredLibrary.length}개의 연구</span>
      </div>
      {loading && <Loading />}
      {!loading && filteredLibrary.length === 0 && (
        <Empty
          icon="library"
          title={query ? "검색 결과가 없습니다" : "첫 논문이 놓일 자리입니다"}
          description={
            query
              ? "검색어를 바꾸어 다시 확인해 주세요."
              : "연구의 최종 확인이 끝나면 원고와 재현 자료가 여기에 나타납니다."
          }
          onStart={query ? undefined : onStart}
        />
      )}
      <div className="library-grid">
        {filteredLibrary.map((entry, index) => {
          const files = entry.files.filter(
            (file) => artifactKind(file) && artifactRequestPath(file),
          );
          return (
            <Card key={entry.id} className="paper-card">
              <CardHeader>
                <div className="paper-topline">
                  <span className="paper-number">PAPER {String(index + 1).padStart(2, "0")}</span>
                  <Badge variant="neutral">검토용 원고</Badge>
                </div>
                <CardTitle className="paper-title">{entry.title}</CardTitle>
                <CardDescription className="repo-label">
                  <GitBranch size={15} />
                  {entry.repository}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {files.length > 0 ? (
                  <div className="artifact-list">
                    {files.map((file) => (
                      <div key={file.url} className="artifact-row">
                        <div>
                          <strong>{artifactKind(file)}</strong>
                          <span>{readableSize(file.size)}</span>
                        </div>
                        <div>
                          {!file.url.endsWith("/bundle") &&
                            artifactKind(file) !== "전체 재현 자료" && (
                              <Button
                                variant="neutral"
                                size="icon-sm"
                                aria-label={`${artifactKind(file)} 열기`}
                                disabled={Boolean(pending)}
                                onClick={() => onFileAction(file, "open")}
                              >
                                <ExternalLink size={15} />
                              </Button>
                            )}
                          <Button
                            variant="neutral"
                            size="icon-sm"
                            aria-label={`${artifactKind(file)} 저장`}
                            disabled={Boolean(pending)}
                            onClick={() => onFileAction(file, "save")}
                          >
                            <Download size={16} />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="field-help">
                    준비된 파일을 읽을 수 없습니다. 상태를 새로고침한 뒤 다시 확인해 주세요.
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
      <p className="library-note">
        자동 생성 원고에는 오류가 남을 수 있습니다. 인용, 결과, 저자 정보는 제출하거나 공유하기 전에
        직접 검토하세요.
      </p>
    </>
  );
}
