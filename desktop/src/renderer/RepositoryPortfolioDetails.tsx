import { inspectRepositoryArticle, inspectRepositoryPortfolioOutputs, inspectRepositoryPortfolioVenueWork, inspectRepositoryPortfolioWork, repositoryPortfolioReasoningReady } from '../shared/publication';
import type { RepositoryPortfolioEvidencePacket, RepositoryPortfolioVenue, ResearchItem } from '../shared/research';
import { getPublicationVenue, PUBLICATION_CATALOG, type PublicationCatalog } from '../shared/venues';
import { Badge } from './components/ui/badge';
import { Button } from './components/ui/button';
import { repositoryCriterionLabels, type ResearchAction } from './research-ui';
import { RepositoryAnalysisDetails } from './RepositoryEvidenceDetails';

const statusLabels: Record<RepositoryPortfolioVenue['status'], string> = {
  pending_analysis: '공통 분석 대기', pending_draft: '원고 작성 대기', writing_interrupted: '작성 요청 기록·결과 대기',
  pending_review: '독립 심사 대기', review_interrupted: '심사 요청 기록·결과 대기',
  content_ready: '학술지별 내용 심사 충족', needs_revision: '내용·근거 보완 필요',
};
const outputLabels = { markdown: 'Markdown', pdf: 'PDF', docx: 'Word' };
const repairOutcomeLabels = { started: '복구 요청 기록·결과 대기', completed: '완료 복구 응답 보존',
  failed: '복구 실패 기록 보존', interrupted: '복구 중단 기록 보존' };
const analysisRevisionLabels = { planned: '계획 보존 · 분석 보완 대기', completed: '분석 보완 완료 · 요구 근거 이행 확인 필요',
  incomplete: '미완료 기록 보존 · 자동 재요청 보류' };

function VenuePaperCard({ venue, job, catalog, locked, runAction }: {
  venue: RepositoryPortfolioVenue; job: ResearchItem; catalog: PublicationCatalog;
  locked: boolean; runAction: ResearchAction;
}) {
  const profile = getPublicationVenue(venue.venue_id, catalog.venues);
  const name = profile?.name ?? venue.venue_id;
  const outputs = inspectRepositoryPortfolioOutputs(venue, job.artifacts, job.authorMetadata);
  const authorOutputCurrent = venue.author_export_status === 'completed' && venue.author_export?.current === true &&
    (['pdf', 'docx'] as const).every(extension => outputs.some(output => output.format === extension &&
      output.artifact.id === venue.author_export?.outputs[extension]?.artifact_id));
  const format = venue.draft ? inspectRepositoryArticle(venue.draft, venue, catalog) : null;
  const assessment = venue.review?.content_assessment;
  const argumentReady = repositoryPortfolioReasoningReady(venue);
  const layoutComplete = venue.layout_export?.status === 'completed' &&
    (['pdf', 'docx'] as const).every(extension => outputs.some(output => output.format === extension &&
      output.artifact.id === venue.layout_export?.outputs?.[extension]?.artifact_id));
  const assessmentLabel = argumentReady && !venue.review!.criteria.presentation.passed
    ? '논증·근거 평가 충족 · 표현·형식 보완 필요' : statusLabels[venue.status];
  const next = inspectRepositoryPortfolioVenueWork(venue, job.portfolioUnsentRequestAvailable);
  const actions = [...new Map([...venue.review?.next_actions ?? [], ...assessment?.next_actions ?? []]
    .map(action => [JSON.stringify(action), action])).values()];
  return <section className="space-y-3 rounded-base border-2 border-border p-3 text-sm" aria-label={`${name} 투고본`}>
    <div className="section-heading">
      <h5 className="font-semibold">{name}</h5>
      <Badge variant="neutral">{assessmentLabel}</Badge>
    </div>
    <p>{venue.article_category}</p>
    <p className="detail-note">내용: {venue.review ? venue.scientific_ready && venue.content_ready ? '평가 충족' : '보완 필요' : '평가 대기'}
      {' · '}제출 파일: {outputs.length === 3 ? '현재 파일 생성됨 · 전체 페이지 확인 필요' : '생성·복구 필요'}
      {' · '}공식 형식: {format?.numericGuidanceVerified ? format.formatReady ? '확인한 수치 충족' : '보완 필요' : '최신 요건 확인 필요'}
      {' · '}저자: {job.authorMetadata ? '정보 보존 · 최종 확인 필요' : '정보 입력·최종 확인 필요'}</p>
    <p className="detail-note">새 원고 작성 {venue.draft_attempts}회 · 보존한 새 원고 {venue.admitted_drafts}개 · 독립 심사 {venue.review_attempts}회</p>
    <p className="detail-note">끊긴 작성 응답 꼬리 복구 {venue.repair_attempts}/1회 · 원래 작성 실패와 횟수 보존</p>
    <p className="detail-note">현재 원고 출력 복구 {venue.export_repair_attempts}/1회 · 누적 출력 복구 {venue.export_repair_total}회 · 원래 출력 실패 기록 보존</p>
    <p className="detail-note">현재 원고 저자 정보 출력 {venue.author_export_attempts}/3회 · 남은 {Math.max(0, 3 - venue.author_export_attempts)}회</p>
    {job.authorMetadata && !authorOutputCurrent && <p className="detail-note" role="status">
      현재 저자 정보가 반영된 PDF·Word가 확인되지 않았습니다. 보존된 이전 파일과 현재 저자 출력 상태를 구분해 확인하세요.
    </p>}
    {authorOutputCurrent && <p className="detail-note">현재 저자 정보를 새 PDF·Word에 반영했습니다. 최종 저자 승인·권리·제출 선언과 전체 페이지 확인은 별도로 필요합니다.</p>}
    {venue.author_export_available && <Button variant="outline" disabled={locked}
      onClick={() => void runAction('portfolio-author', () => window.paperFactory.exportRepositoryPortfolioAuthor(job.id, venue.venue_id))}>
      {name} 저자 정보 반영해 출력</Button>}
    {venue.author_export && <section className="detail-note space-y-2" aria-label={`${name} 저자 정보 출력 결과`}>
      <p>저자 정보 출력 {authorOutputCurrent ? '현재본 완료' : '미완료 또는 현재 정보와 불일치'} · 모델 요청 0회 · 본문·심사·연구 횟수 보존</p>
      {venue.author_export.errors.map((error, index) => <p key={index}>{outputLabels[error.format]}: {error.message}</p>)}
    </section>}
    {venue.author_export_status === 'stale' && <p className="detail-note">이전 저자 출력은 현재 저자 정보·원고·심사·출력 원문과 달라 현재 제출 파일로 선택하지 않습니다.</p>}
    {venue.author_export_status === 'interrupted' && <p className="detail-note">저자 출력 중단 기록과 사용 횟수를 보존했습니다. 완료 파일로 표시하지 않습니다.</p>}
    <p className="detail-note">남은 새 원고 작성 {Math.max(0, 3 - venue.draft_attempts)}회 · 남은 독립 심사 {Math.max(0, 3 - venue.review_attempts)}회</p>
    {venue.draft && <p className="detail-note">{venue.revise_reason}</p>}
    {!!venue.export?.original_artifact_id && <p className="detail-note">복구 출력과 별도로 원래 변환 실패 영수증을 보존했습니다.</p>}
    {(venue.repair_binding || venue.repair_attempts > 0) && <section className="detail-note space-y-2" aria-label={`${name} 응답 꼬리 복구`}>
      <p>{venue.repair_outcome ? repairOutcomeLabels[venue.repair_outcome] : venue.repair_binding ? '꼬리 복구 대기' : '꼬리 복구 시도 기록 보존'}</p>
      {next.action === 'repair' && <p>{next.reason}</p>}
    </section>}
    {venue.draft ? <p className="font-semibold whitespace-pre-wrap">{venue.draft.title}</p>
      : <p className="detail-note">이 학술지용 실제 원고는 아직 없습니다.</p>}
    {venue.draft && !venue.analysis_current && <p className="detail-note">공통 분석 보완 전 원고·심사 기록입니다. 기존 파일과 평가를 보존하며 과거 충족 판정을 최신 분석 기준의 준비도로 사용하지 않습니다.</p>}
    {venue.review ? <details open={!venue.scientific_ready || !venue.content_ready} className="space-y-3">
      <summary className="font-semibold">학술지별 독립 심사 · {assessmentLabel}</summary>
      {argumentReady && !venue.review.criteria.presentation.passed && <p className="detail-note">
        논증·근거와 비교·기여는 충족했습니다. 원 심사의 표현·구성 지적은 아래 이유와 보완 요구에서 확인해야 합니다.
        {layoutComplete ? ' 참고문헌 경로·Word 표 번호의 출력 보완은 완료했고, 새 출력의 전체 페이지 확인은 별도로 필요합니다.'
          : ' 아래 출력 보완 결과와 구분해 표시합니다.'}
      </p>}
      <dl className="mt-3 space-y-3">{Object.entries(venue.review.criteria).map(([key, criterion]) => <div key={key}>
        <dt className="font-semibold">{repositoryCriterionLabels[key as keyof typeof repositoryCriterionLabels]} · {criterion.passed ? '충족' : '미충족'}</dt>
        <dd className="detail-note mt-1 whitespace-pre-wrap">{criterion.reason}</dd>
      </div>)}</dl>
      {assessment && <dl className="space-y-3">{(['comparison', 'contribution'] as const).map(key => <div key={key}>
        <dt className="font-semibold">{key === 'comparison' ? '직접 선행 비교' : '학술지에 필요한 기여'} · {assessment[key].passed ? '충족' : '미충족'}</dt>
        <dd className="detail-note mt-1 whitespace-pre-wrap">{assessment[key].reason}</dd>
      </div>)}</dl>}
      {!!venue.review.issues.length && <ul className="list-disc space-y-1 pl-5">{venue.review.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>}
      {!!assessment?.issues.length && <ul className="list-disc space-y-1 pl-5">{assessment.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>}
    </details> : <p className="detail-note">이 투고본의 독립 심사 기록은 아직 없습니다.</p>}
    {!!actions.length && <section className="space-y-2" aria-label={`${name} 필요한 근거와 다음 작업`}>
      <h6 className="font-semibold">필요한 근거·다음 작업</h6>
      {actions.map((action, index) => <div key={index}>
        <p className="font-semibold">{action.target}</p>
        <p className="whitespace-pre-wrap">{action.required_change}</p>
        <p className="detail-note whitespace-pre-wrap">확인 방법: {action.verification}</p>
      </div>)}
    </section>}
    {format && <details className="detail-note"><summary>투고처 형식 점검 · 본문 추산 {format.estimatedWords}단어</summary>
      <p className="mt-2">초록 {format.abstractWords}단어 · 참고문헌 {format.references}개</p>
      <ul className="mt-2 list-disc space-y-1 pl-5">{[...format.blockers, ...format.uncheckedRequirements].map((item, index) => <li key={index}>{item}</li>)}</ul>
    </details>}
    {outputs.length ? <div className="space-y-2" aria-label={`${name} 실제 출력 파일`}>
      {outputs.map(({ format: extension, artifact }) => <div key={artifact.id} className="action-row">
        <span>{outputLabels[extension]} · {artifact.size.toLocaleString('ko-KR')} 바이트</span>
        <Button variant="outline" size="sm" disabled={locked} onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, artifact.id))}>
          {name} {outputLabels[extension]} 저장</Button>
        <Button variant="ghost" size="sm" disabled={locked} onClick={() => void runAction('open', () => window.paperFactory.openArtifact(job.id, artifact.id))}>
          {name} {outputLabels[extension]} 열기</Button>
      </div>)}
    </div> : <p className="detail-note">보존된 실제 출력 파일은 아직 없습니다.</p>}
    {venue.format_export_available && <Button variant="outline" disabled={locked}
      onClick={() => void runAction('portfolio-format', () => window.paperFactory.reformatRepositoryPortfolioDraft(job.id, venue.venue_id))}>
      {name} 참고문헌 중복 정리해 출력</Button>}
    {venue.format_export && <section className="detail-note space-y-2" aria-label={`${name} 참고문헌 출력 정리`}>
      <p>참고문헌 출력 정리 {venue.format_export.status === 'completed' ? '완료' : '미완료'} · {venue.format_export_attempts}/1회</p>
      <p>과학 본문·원고·기존 심사와 횟수를 보존했습니다. 새 출력의 전체 페이지 확인이 필요합니다.</p>
      {venue.format_export.errors.map((error, index) => <p key={index}>{outputLabels[error.format]}: {error.message}</p>)}
    </section>}
    {venue.format_export_attempts > 0 && !venue.format_export && <p className="detail-note">
      참고문헌 출력 정리 {venue.format_export_attempts}/1회 기록 · 완료 영수증 없음. 기존 원고·심사를 보존하며 자동 재시도하지 않습니다.
    </p>}
    {venue.layout_export_available && <Button variant="outline" disabled={locked}
      onClick={() => void runAction('portfolio-layout', () => window.paperFactory.correctRepositoryPortfolioLayout(job.id, venue.venue_id))}>
      {name} 참고문헌 경로·Word 표 번호 보완해 출력</Button>}
    {venue.layout_export && <section className="detail-note space-y-2" aria-label={`${name} 원고 출력 보완`}>
      <p>참고문헌 경로·Word 표 번호 보완 {venue.layout_export.status === 'completed' ? '완료' : '미완료'} · {venue.layout_export_attempts}/1회</p>
      <p>기존 원고·심사·출력과 과학 본문·저자 정보를 보존했습니다. 전체 페이지 확인은 별도로 필요합니다.</p>
      {venue.layout_export.errors.map((error, index) => <p key={index}>{outputLabels[error.format]}: {error.message}</p>)}
    </section>}
    {venue.layout_export_attempts > 0 && !venue.layout_export && <p className="detail-note">
      원고 출력 보완 {venue.layout_export_attempts}/1회 기록 · 완료 영수증 없음. 기존 파일을 보존하며 자동 재시도하지 않습니다.
    </p>}
    {profile && <a href={profile.guidelines_url} target="_blank" rel="noreferrer" className="detail-note underline">{name} 공식 제출 안내</a>}
    {!next.action && <p className="detail-note">{next.reason}</p>}
    {(venue.export_status === 'failed' || venue.export_status === 'interrupted') && <section className="detail-note space-y-2" aria-label={`${name} 출력 변환 진단`}>
      <p>출력 변환 {venue.export_status === 'failed' ? '실패' : '중단'} 기록 보존</p>
      <p>{next.action === 'repair_export' ? next.reason : venue.export_repair_attempts > 0
        ? '출력 복구 1회 한도를 사용했습니다. 같은 복구를 다시 실행하지 않습니다.'
        : '확인된 출력 복구 조건이 없어 같은 변환을 자동으로 다시 실행하지 않습니다.'}</p>
      {venue.export?.errors.map((error, index) => <p key={index} className="whitespace-pre-wrap">{outputLabels[error.format]}: {error.message}</p>)}
    </section>}
  </section>;
}

export function RepositoryPortfolioDetails({ job, disabled, locked, runAction }: {
  job: ResearchItem; disabled: boolean; locked: boolean; runAction: ResearchAction;
}) {
  const paper = job.repositoryPaper;
  if (job.researchMode !== 'repository_analysis' || !paper) return null;
  const portfolio = paper.portfolio;
  const catalog = paper.publication_venues ?? PUBLICATION_CATALOG;
  const next = inspectRepositoryPortfolioWork(paper, job.portfolioUnsentRequestAvailable);
  const available = ['repository_planned', 'repository_manuscript'].includes(job.stage) && next.action !== null;
  const outputsComplete = portfolio?.venues.every(venue => inspectRepositoryPortfolioOutputs(venue, job.artifacts, job.authorMetadata).length === 3);
  const finished = portfolio?.all_content_ready && outputsComplete;
  return <section className="space-y-3 rounded-base border-2 border-border p-3 text-sm" aria-label="IEEE 매체별 투고본">
    <div className="section-heading">
      <h4 className="font-semibold">공통 분석 → IEEE 매체별 실제 투고본</h4>
      {portfolio && <Badge variant="neutral">개별 심사 기록 {portfolio.completed}/{portfolio.total}</Badge>}
    </div>
    <p className="detail-note">공통 소스 분석에서 적합한 IEEE Software·Security &amp; Privacy Feature Article을 작성합니다. 각 매체의 독자·실무 문제·교훈에 맞춰 설명하고 별도로 평가합니다. 보안·프라이버시 소재가 없으면 해당 원고를 강제로 만들지 않습니다.</p>
    <p className="detail-note">아래 횟수는 학술지별 새 작업이며 실패·중단한 모델 요청도 포함합니다. 내용 심사 충족은 저자 승인·최신 제출 요건 확인·학술지 채택을 의미하지 않습니다.</p>
    {!finished && <Button variant="outline" disabled={disabled || !available}
      onClick={() => void runAction('portfolio', () => window.paperFactory.requestRepositoryPortfolio(job.id))}>
      {portfolio ? 'IEEE 매체별 미완료 투고본 재개' : 'IEEE 매체별 투고본 작성 시작'}
    </Button>}
    {!available && <p className="detail-note">{next.reason}</p>}
    {portfolio && <>
      <p className="detail-note">논증·근거 평가 충족 {portfolio.venues.filter(repositoryPortfolioReasoningReady).length}/{portfolio.total} · 보존된 전체 심사 기준 충족 {portfolio.venues.filter(venue => venue.scientific_ready && venue.content_ready).length}/{portfolio.total}</p>
      <p className="detail-note">공통 소스 분석 {portfolio.analysis ? '보존됨' : '대기'} · {portfolio.all_content_ready ? '생성한 개별 원고의 내용 심사 충족' : '매체별 준비도와 필요한 근거를 아래에서 확인하세요.'}</p>
      {(portfolio.analysis_revision_required || portfolio.analysis_revision) && <section className="space-y-3" aria-label="공통 연구 보완 계획">
        <h5 className="font-semibold">실제 독립 심사에 따른 공통 연구 보완</h5>
        <p className="detail-note">전체 분석 예산 남은 {Math.max(0, 3 - paper.analysis_attempts)}회 · 기존 분석·원고·심사·실험 기록 보존</p>
        {portfolio.analysis_revision ? <>
          <p>{analysisRevisionLabels[portfolio.analysis_revision.status]}</p>
          <p className="detail-note">관련 학술지: {portfolio.analysis_revision.affected_venues.map(id => getPublicationVenue(id, catalog.venues)?.name ?? id).join(' · ')}</p>
          {portfolio.analysis_revision.actions.map((action, index) => <div key={index}>
            <p className="font-semibold">{action.target}</p>
            <p className="whitespace-pre-wrap">{action.required_change}</p>
            <p className="detail-note whitespace-pre-wrap">확인 방법: {action.verification}</p>
          </div>)}
        </> : <p className="detail-note">보존된 학술지별 심사가 소스 분석 보완을 요구했습니다. 기존 미완료 작성·심사·꼬리 복구를 정리한 뒤 남은 예산 안에서 계획을 보존합니다.</p>}
        <p className="detail-note">분석 보완 완료는 필요한 근거의 확보나 개별 원고의 실무 기여 충족을 뜻하지 않습니다.</p>
      </section>}
      <p className="detail-note">선행 본문 PDF 예약: 기존 {portfolio.pdf_budget.base_used}회 · 공통 보강 {portfolio.pdf_budget.additional_used}/{portfolio.pdf_budget.additional_limit}회 · 합산 {portfolio.pdf_budget.total_used}회. 기존 예약과 실패 기록을 보존합니다.</p>
      <p className="detail-note">공통 문헌 확보 {portfolio.literature_budget.used}/{portfolio.literature_budget.limit}회 · 남은 {Math.max(0, portfolio.literature_budget.limit - portfolio.literature_budget.used)}회. 최초 문헌과 실패·중단 기록을 포함하며 새 자료 확보로 기존 횟수를 초기화하지 않습니다.</p>
      <section className="space-y-2" aria-label="실제 보완 연구자료">
        <h5 className="font-semibold">실제 보완 연구자료</h5>
        <p className="detail-note">자료 등록 {portfolio.supplementary_evidence_budget.used}/{portfolio.supplementary_evidence_budget.limit}회 · 기존 문헌 확보·분석·원고·심사 횟수 보존</p>
        <p className="detail-note">원문과 출처, 비교 방법·결과를 담은 보완 자료를 같은 연구에 등록합니다. 등록한 자료는 다음 원고 작성·독립 심사에 전달하며 현재 충족 판정을 바꾸지 않습니다.</p>
        {portfolio.supplementary_evidence_available && <label className="block space-y-1">
          <span className="font-semibold">실제 보완 연구자료 패키지</span>
          <input type="file" aria-label="실제 보완 연구자료 패키지" accept=".json,application/json" disabled={locked}
            onChange={event => {
              const file = event.currentTarget.files?.[0];
              event.currentTarget.value = '';
              if (!file) return;
              void runAction('portfolio-evidence', async () => {
                if (file.size > 2 * 1024 * 1024) throw new Error('보완 자료 패키지는 2 MiB까지 지원합니다.');
                const packet = JSON.parse(await file.text()) as RepositoryPortfolioEvidencePacket;
                return window.paperFactory.admitRepositoryPortfolioEvidence(job.id, packet);
              });
            }} />
          <span className="detail-note block">완전한 원문 파일 1–32개가 포함된 JSON · 일반 텍스트 128 KiB, 정확한 commit 비교 소스 256 KiB, 텍스트 합계 512 KiB · 원 증명에 결속된 출판사 PDF 별도 합계 1 MiB · 전체 요청 2 MiB 이내</span>
        </label>}
        {portfolio.supplementary_evidence && <details className="detail-note">
          <summary>보완 자료 {portfolio.supplementary_evidence.status === 'admitted' ? '등록 완료' : '미완료 기록 보존'}</summary>
          <p className="mt-2">관련 학술지: {portfolio.supplementary_evidence.affected_venues.map(id => getPublicationVenue(id, catalog.venues)?.name ?? id).join(' · ')}</p>
          {portfolio.supplementary_evidence.selection && <>
            <p className="whitespace-pre-wrap">선정 이유: {portfolio.supplementary_evidence.selection.rationale}</p>
            <p className="whitespace-pre-wrap">자료 출처: {portfolio.supplementary_evidence.selection.lineage}</p>
          </>}
          {portfolio.supplementary_evidence.comparison && <p className="whitespace-pre-wrap">비교 방법: {portfolio.supplementary_evidence.comparison.protocol}</p>}
          <ul className="mt-2 space-y-1">{portfolio.supplementary_evidence.materials.map(material => <li key={material.id}>
            <a href={material.url} target="_blank" rel="noreferrer" className="underline">{material.title}</a>
            <span> · {material.size.toLocaleString('ko-KR')} 바이트</span>
          </li>)}</ul>
          <p className="mt-2">비교 결과는 제공된 해석으로 보존합니다. 코드 실행·사람 검증이나 독립 심사 통과를 뜻하지 않습니다.</p>
        </details>}
      </section>
      <p className="detail-note">충족 수는 아래 최신 원고 각각의 내부 평가입니다. 원고 내용, 실제 제출 파일과 저자 확인을 따로 표시하며, 학술지의 실제 심사 결과를 뜻하지 않습니다.</p>
      {portfolio.literature_followup_available && <p className="detail-note">실제 심사의 미해결 비교 질문에 대한 추가 문헌 확보가 가능합니다. 확보한 원문과 최신 분석을 읽은 새 원고·독립 심사로 학술지별 준비도를 다시 평가합니다.</p>}
      {portfolio.analysis && <details className="space-y-3"><summary className="font-semibold">IEEE 매체용 공통 소스 분석</summary>
        <div className="mt-3"><RepositoryAnalysisDetails paper={portfolio} /></div>
      </details>}
      {!!portfolio.literature_collections.length && <details className="detail-note"><summary>공통 보강 문헌 확보 기록</summary>
        <ul className="mt-2 space-y-2">{portfolio.literature_collections.map(collection => <li key={collection.artifact_id}>
          <p>보강 문헌 회수 {collection.attempt}회 · {collection.status === 'completed' ? '자료 확보 기록 보존' : '중단 기록 보존'}</p>
          <p className="whitespace-pre-wrap">검색 질문: {collection.queries.join(' · ')}</p>
        </li>)}</ul>
      </details>}
      {portfolio.guidance && <details className="detail-note"><summary>학술지 공식 안내 확보 기록</summary>
        <ul className="mt-2 space-y-2">{portfolio.guidance.sources.map(source => <li key={`${source.venue_id}:${source.url}`}>
          <p>{getPublicationVenue(source.venue_id, catalog.venues)?.name ?? source.venue_id} · {source.status === 'retained' ? '본문 보존' : '확보 실패'}</p>
          <a href={source.url} target="_blank" rel="noreferrer" className="break-all underline">{source.url}</a>
          {source.failure && <p className="whitespace-pre-wrap">{source.failure}</p>}
        </li>)}</ul>
      </details>}
      {portfolio.venues.map(venue => <VenuePaperCard key={venue.venue_id} venue={venue} job={job} catalog={catalog} locked={locked} runAction={runAction} />)}
    </>}
  </section>;
}
