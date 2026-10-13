import { useEffect, useState } from "react";
import { Download, ExternalLink } from "lucide-react";
import { NEW_RESEARCH_MODE } from "../shared/publication";
import type { RepositoryPublicationStatus } from "../shared/publication";
import type { AuthorMetadataInput, ResearchItem } from "../shared/research";
import { Button } from "./components/ui/button";
import type { ResearchAction } from "./research-ui";

const outputLabels: Record<string, string> = {
  "export-pdf": "PDF", "export-docx": "Word", "export-md": "Markdown",
  "export-tex": "LaTeX", reproducibility: "재현 패키지 ZIP",
};
const resultFileLabel = (id: string) => {
  const match = /^repository-draft-(md|pdf|docx)-([1-3])(?:-format-([1-3]))?$/.exec(id);
  return outputLabels[id] ?? (match ? `원고 ${match[2]} · ${{ md: "Markdown", pdf: "PDF", docx: "Word" }[match[1]]}${match[3] ? ` · 출력 보완 ${match[3]}` : ""}` : null);
};
function ArtifactActions({ jobId, artifacts, locked, runAction }: {
  jobId: string; artifacts: ResearchItem["artifacts"]; locked: boolean; runAction: ResearchAction;
}) {
  return <>{artifacts.map(artifact => {
    const label = resultFileLabel(artifact.id);
    if (!label) return null;
    return <div key={artifact.id} className="space-y-2">
      <p className="text-sm">{label} · {artifact.size.toLocaleString("ko-KR")} 바이트</p>
      <div className="action-row">
        <Button variant="outline" size="sm" disabled={locked} onClick={() => void runAction("save", () => window.paperFactory.saveArtifact(jobId, artifact.id))}>
          <Download aria-hidden="true" /> {label} 저장</Button>
        <Button variant="ghost" size="sm" disabled={locked} onClick={() => void runAction("open", () => window.paperFactory.openArtifact(jobId, artifact.id))}>
          {label} 열기 <ExternalLink aria-hidden="true" /></Button>
      </div>
    </div>;
  })}</>;
}

export function AuthorMetadataEditor({ job, disabled, runAction }: { job: ResearchItem; disabled: boolean; runAction: ResearchAction }) {
  const [value, setValue] = useState<AuthorMetadataInput>(job.authorMetadata?.value ?? { display_name: "", email: "", affiliation: "" });
  useEffect(() => { setValue(job.authorMetadata?.value ?? { display_name: "", email: "", affiliation: "" }); }, [job.authorMetadata]);
  const available = job.researchMode === NEW_RESEARCH_MODE && job.stage === "repository_manuscript" &&
    job.manuscriptAvailable && ["ready", "blocked"].includes(job.status);
  if (!available) return null;
  return <details className="rounded-base border-2 border-border p-3 text-sm">
    <summary className="font-semibold">실제 저자 정보 입력</summary>
    <p className="detail-note mt-2">저자 정보를 저장한 뒤 각 매체의 ‘저자 정보 반영해 출력’을 누르면 새 PDF·Word에 반영합니다. 원래 본문·원고·심사·횟수와 이전 파일은 보존됩니다. 정보 저장은 저자 승인이나 실제 투고를 의미하지 않습니다.</p>
    <form className="mt-3 space-y-3" onSubmit={event => { event.preventDefault(); void runAction("author", () => window.paperFactory.setResearchAuthorMetadata(job.id, value)); }}>
      {([['display_name', '저자 이름'], ['email', '저자 이메일'], ['affiliation', '저자 소속'], ['orcid', 'ORCID (선택)']] as const).map(([key, label]) =>
        <div className="field" key={key}><label htmlFor={`${job.id}-${key}`}>{label}</label>
          <input id={`${job.id}-${key}`} type={key === "email" ? "email" : "text"} required={key !== "orcid"} value={value[key] ?? ""} disabled={disabled}
            onChange={event => setValue(current => ({ ...current, [key]: event.target.value }))} /></div>)}
      <Button type="submit" variant="outline" disabled={disabled || !value.display_name.trim() || !value.email.trim() || !value.affiliation.trim()}>저자 정보 저장</Button>
    </form>
  </details>;
}

export function ResearchOutputs({ job, publication, locked, analysisReady, runAction }: {
  job: ResearchItem; publication: RepositoryPublicationStatus | null; locked: boolean;
  analysisReady: boolean; runAction: ResearchAction;
}) {
  const resultArtifacts = job.stage === "exported" || job.researchMode === NEW_RESEARCH_MODE
    ? job.artifacts.filter(artifact => resultFileLabel(artifact.id)) : [];
  if (!resultArtifacts.length) return null;
  const artifacts = new Map(resultArtifacts.map(artifact => [artifact.id, artifact]));
  const currentOutputIds = publication ? [job.repositoryPaper?.artifact_ids.draft_markdown, ...publication.currentOutputIds]
    .filter((id): id is string => !!id && artifacts.has(id)) : [];
  const currentIds = new Set(currentOutputIds);
  const previousOutputIds = publication ? [...new Set([...publication.previousOutputIds, ...artifacts.keys()])]
    .filter(id => !currentIds.has(id)) : [];
  const outputArtifacts = (ids: string[]) => ids.flatMap(id => {
    const artifact = artifacts.get(id);
    return artifact ? [artifact] : [];
  });
  const formattingBlockers = [
    ...(!job.repositoryPaper?.draft || !job.repositoryPaper.artifact_ids.draft_markdown ||
      !job.artifacts.some(artifact => artifact.id === job.repositoryPaper?.artifact_ids.draft_markdown)
      ? ["현재 원고와 Markdown 출력 원문을 확인해야 합니다."] : []),
    ...(!["ready", "blocked"].includes(job.status) ? ["원고를 보존한 뒤 출력할 수 있습니다."] : []),
    ...(locked ? ["진행 중인 작업이 끝난 뒤 출력할 수 있습니다."] : []),
    ...(!analysisReady ? ["로컬 연구 엔진을 확인해야 합니다."] : []),
    ...(publication?.formattingRemaining === 0 ? ["현재 원고의 출력 다시 생성 3회를 모두 사용했습니다."] : []),
  ];
  return <div className="space-y-3 border-t-2 border-border pt-3">
    <h4 className="font-semibold">생성된 결과 파일</h4>
    <p className="detail-note">완료 상태와 모델의 검토 통과는 학술지 심사나 채택을 의미하지 않습니다. 제출 전 원문 문헌·실험 설계·연구 기여를 직접 확인해 주세요.</p>
    <div className="action-row">
      <Button variant="outline" size="sm" disabled={locked}
        onClick={() => void runAction("folder", () => window.paperFactory.showArtifactFolder(job.id,
          resultArtifacts[0].id))}>결과 폴더 열기</Button>
      {job.researchMode === "repository_analysis" && job.stage === "repository_manuscript" && job.manuscriptAvailable && (
        <Button variant="outline" size="sm" disabled={formattingBlockers.length > 0}
          onClick={() => void runAction("reformat", () => window.paperFactory.reformatResearchDraft(job.id))}>출력 다시 생성</Button>
      )}
    </div>
    {job.researchMode === "repository_analysis" && job.manuscriptAvailable && <p className="detail-note">출력 다시 생성은 보존된 원고로 PDF·Word 파일만 만듭니다. 원고마다 최대 3회이며, 기존 원고·심사·횟수와 이전 출력은 보존됩니다.</p>}
    {publication && <>
      <p className="detail-note">현재 원고의 출력 다시 생성: {publication.formattingRemaining}/3회 남음.</p>
      {!publication.authorOutputCurrent && job.authorMetadata && <p className="detail-note" role="status">현재 PDF·Word에 최신 저자 정보가 반영되었는지 확인되지 않았습니다. 출력 다시 생성 후 새 파일을 확인하세요.</p>}
      {!!formattingBlockers.length && <p className="detail-note">출력 다시 생성 대기: {formattingBlockers.join(" ")}</p>}
    </>}
    {job.repositoryPaper?.formatting_receipts?.filter(receipt => receipt.draft_attempt === job.draftAttempt).map(receipt =>
      <p key={receipt.artifact_id} className="detail-note">출력 보완 {receipt.attempt} · {receipt.status === "completed" ? "기록 보존됨" : "시도 예약됨"}
        {receipt.errors.map(error => ` · ${error.format}: ${error.message}`).join("")}</p>)}
    {publication ? <>
      <section className="space-y-3" aria-label="현재 원고 출력">
        <h5 className="font-semibold">현재 원고 출력</h5>
        {!publication.outputCurrent && <p className="detail-note">현재 원고에 결합된 PDF·Word 출력이 모두 확인되지 않았습니다. 보존된 파일은 아래에서 확인할 수 있습니다.</p>}
        <ArtifactActions jobId={job.id} artifacts={outputArtifacts(currentOutputIds)} locked={locked} runAction={runAction} />
      </section>
      {!!previousOutputIds.length && <details className="space-y-3" aria-label="이전 출력 파일">
        <summary className="font-semibold">이전 출력 파일 {previousOutputIds.length}개</summary>
        <ArtifactActions jobId={job.id} artifacts={outputArtifacts(previousOutputIds)} locked={locked} runAction={runAction} />
      </details>}
    </> : <ArtifactActions jobId={job.id} artifacts={resultArtifacts} locked={locked} runAction={runAction} />}
  </div>;
}
