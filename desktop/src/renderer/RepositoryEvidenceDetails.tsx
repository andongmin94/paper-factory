import type { RepositoryPaperProgress } from '../shared/research';
import { getPublicationVenue, PUBLICATION_CATALOG } from '../shared/venues';

const fitLabels = { suitable: '적합', needs_evidence: '추가 근거 필요', out_of_scope: '범위 밖' };

export function RepositoryTargetDetails({ paper }: { paper: RepositoryPaperProgress }) {
  const target = paper.plan?.publication_target;
  const catalog = paper.publication_venues ?? PUBLICATION_CATALOG;
  const venue = getPublicationVenue(target?.venue_id, catalog.venues);
  const format = paper.venueFormat;
  if (!target || !venue) return <section className="space-y-2" aria-label="투고처 선택">
    <h5 className="font-semibold">투고처 선택 기록 없음</h5>
    <p className="detail-note">이 연구에는 두 IEEE 매체의 적합성과 투고처 선택 기록이 없습니다. 먼저 실제 저장소의 소재와 근거를 평가해야 합니다.</p>
  </section>;
  const limits = venue.verified_limits;
  const measure = (value: number, maximum: number | undefined, unit: string) =>
    `${value.toLocaleString('ko-KR')}${maximum === undefined ? '' : `/${maximum.toLocaleString('ko-KR')}`}${unit}`;
  return <>
    <section className="space-y-2" aria-label="선택한 투고처">
      <h5 className="font-semibold">투고 목표 · {venue.name}</h5>
      <p>{target.article_category}</p>
      <p className="whitespace-pre-wrap">선택 이유: {target.selection_reason}</p>
      <p className="detail-note whitespace-pre-wrap">기여 기준: {venue.contribution_expectation}</p>
      <p className="detail-note whitespace-pre-wrap">분석 기준: {venue.analysis_expectation}</p>
      <a href={venue.guidelines_url} target="_blank" rel="noreferrer" className="underline">{venue.name} 공식 작성 안내</a>
      <p className="detail-note">자료 기준일 {catalog.checked_at}. {catalog.recognition.note}</p>
      <details className="detail-note"><summary>두 IEEE 매체 적합성 비교</summary>
        <dl className="mt-2 space-y-3">{target.candidates.map(candidate => <div key={candidate.venue_id}>
          <dt className="font-semibold">{getPublicationVenue(candidate.venue_id, catalog.venues)?.name ?? candidate.venue_id} · {fitLabels[candidate.fit]}</dt>
          <dd className="mt-1 whitespace-pre-wrap">{candidate.reason}</dd>
          {!!candidate.missing_evidence.length && <dd className="mt-1">필요한 근거: {candidate.missing_evidence.join(' · ')}</dd>}
        </div>)}</dl>
      </details>
    </section>
    {format && <section className="space-y-2" aria-label="투고처 형식 점검">
      <h5 className="font-semibold">확인한 형식 요건 · {format.formatReady ? '충족' : '보완 필요'}</h5>
      <dl className="grid gap-1 sm:grid-cols-2">{[
        ['본문 분량 추산', measure(format.estimatedWords, limits.max_words, '단어')],
        ['초록', measure(format.abstractWords, limits.max_abstract_words, '단어')],
        ['참고문헌', measure(format.references, limits.max_references, '개')],
        ...(limits.insight_count === undefined ? [] : [['실무 적용 교훈', measure(format.insights, limits.insight_count, '개')]]),
      ].map(([label, value]) => <div key={label}><dt className="inline font-semibold">{label}: </dt><dd className="inline">{value}</dd></div>)}</dl>
      <p className="detail-note">그림 {format.figures}개·표 {format.tables}개.
        {limits.visual_word_cost === undefined ? ' 표 내용과 그림 설명을 실제 단어 수에 포함한 추산입니다.' : ` 그림·표마다 ${limits.visual_word_cost}단어를 포함한 추산입니다.`}
        {' '}내용 품질과 공식 제출 요건·저자 확인은 별도로 평가합니다.</p>
      {!!format.blockers.length && <ul className="list-disc space-y-1 pl-5">{format.blockers.map((blocker, index) => <li key={index}>{blocker}</li>)}</ul>}
      {format.uncheckedRequirements.map((item, index) => <p key={index} className="detail-note">{item}</p>)}
    </section>}
  </>;
}

export function RepositoryAnalysisDetails({ paper }: { paper: Pick<RepositoryPaperProgress, 'analysis'> }) {
  const analysis = paper.analysis;
  if (!analysis) return <p className="detail-note">별도 분석 결과 기록 없음. 계획과 실제 분석 결과는 구분해 확인해야 합니다.</p>;
  return <section className="space-y-3" aria-label="실제 소스 분석 결과">
    <h5 className="font-semibold">실제 분석 · {analysis.units.length}개 단위 · {analysis.findings.length}개 발견</h5>
    <p className="whitespace-pre-wrap">{analysis.method}</p>
    <details className="detail-note"><summary>분석 기준과 실제 관측</summary>
      <dl className="mt-2 space-y-2">{analysis.codebook.map(item => <div key={item.dimension}>
        <dt className="font-semibold">{item.dimension}</dt><dd className="whitespace-pre-wrap">{item.definition}</dd>
      </div>)}</dl>
      <div className="mt-3 space-y-3">{analysis.units.map(unit => <section key={unit.id} className="space-y-2">
        <h6 className="font-semibold">{unit.id} · {unit.label}</h6>
        <p>근거: {unit.evidence_ids.join(', ')}</p>
        <ul className="list-disc space-y-2 pl-5">{unit.observations.map((observation, index) => <li key={index}>
          <p className="whitespace-pre-wrap">{observation.dimension}: {observation.finding}</p>
          <p>관측 근거: {observation.evidence_ids.join(', ')}</p>
        </li>)}</ul>
      </section>)}</div>
    </details>
    <dl className="space-y-3">{analysis.findings.map(finding => <div key={finding.id}>
      <dt className="font-semibold whitespace-pre-wrap">{finding.id} · {finding.claim}</dt>
      <dd className="detail-note mt-1">분석 단위: {finding.unit_ids.join(', ')} · 원문 근거: {finding.evidence_ids.join(', ')}</dd>
      <dd className="detail-note mt-1 whitespace-pre-wrap">한계: {finding.limitations}</dd>
    </div>)}</dl>
    <details className="detail-note"><summary>반례·적용 한계와 보존한 인용</summary>
      <ul className="mt-2 space-y-3">{analysis.counterexamples.map((item, index) => <li key={index}>
        <p className="font-semibold">{item.finding_id}: {item.condition}</p>
        <p className="whitespace-pre-wrap">{item.implication}</p><p>근거: {item.evidence_ids.join(', ')}</p>
      </li>)}</ul>
      {analysis.source_evidence.map(item => <details key={item.id} className="mt-2">
        <summary>{item.id} · {item.path}</summary>
        <p className="break-all">SHA-256: {item.sha256}</p>
        <blockquote className="mt-1 whitespace-pre-wrap">{item.quote}</blockquote>
        <p className="mt-1 whitespace-pre-wrap">{item.interpretation}</p>
      </details>)}
      <ul className="mt-2 list-disc pl-5">{analysis.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
    </details>
  </section>;
}
