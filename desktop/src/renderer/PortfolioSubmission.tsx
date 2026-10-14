import { useEffect, useState } from 'react';
import type { ResearchItem } from '../shared/research';
import type { PortfolioSubmissionCandidate, PortfolioSubmissionConfirmationInput,
  PortfolioSubmissionPreparation, PortfolioSubmissionRecordInput, PortfolioSubmissionState } from '../shared/submission';
import { Badge } from './components/ui/badge';
import { Button } from './components/ui/button';
import type { ResearchAction } from './research-ui';

const statusLabels: Record<PortfolioSubmissionState['status'], string> = {
  awaiting_file_check: '새 제출 파일 · 직접 검수 대기', generation_failed: '새 제출 파일 생성 실패',
  not_started: '투고 준비 전', prepared: '투고 패키지 준비됨', stale: '원고 변경 · 다시 확인 필요',
  submitted: '접수 기록 · 사용자 확인', withdrawn: '철회 기록 · 사용자 확인', rejected: '불채택 기록 · 사용자 확인',
};
const declarationLabels: Record<keyof PortfolioSubmissionConfirmationInput['declarations'], string> = {
  identity_confirmed: '저자 이름·소속·이메일·약력과 제공한 사진이 실제 저자 정보와 일치합니다.',
  all_authors_approved: '원고에 기재된 모든 저자가 이 원고와 투고를 승인했습니다.',
  originality_confirmed: '중복 게재와 다른 학술지의 동시 심사에 해당하지 않습니다.',
  rights_confirmed: '인용·코드·표·그림·사진의 사용 권리와 필요한 허가를 확인했습니다.',
  ai_disclosure_reviewed: '원고의 AI 사용 공시를 확인하고 저자가 해석과 내용에 책임집니다.',
  guidelines_reviewed: '선택한 학술지의 최신 안내와 실제 투고 유형·필수 항목을 확인했습니다.',
  all_pages_reviewed: '아래 새 Word·PDF의 모든 페이지, 인용·수치·표·그림을 직접 확인했습니다.',
};
const emptyDeclarations = (): PortfolioSubmissionConfirmationInput['declarations'] => ({
  identity_confirmed: false, all_authors_approved: false, originality_confirmed: false,
  rights_confirmed: false, ai_disclosure_reviewed: false, guidelines_reviewed: false, all_pages_reviewed: false,
});
const qaLabels: Record<keyof PortfolioSubmissionConfirmationInput['qa'], string> = {
  word_count: '실제 Word에서 확인한 단어 수', docx_pages: '확인한 Word 전체 페이지 수',
  pdf_pages: '확인한 PDF 전체 페이지 수', table_count: '표 개수', figure_count: '그림 개수',
};

async function photoInput(file: File | null) {
  if (!file) return null;
  if (file.size > 512 * 1024 || !['image/png', 'image/jpeg'].includes(file.type)) {
    throw new Error('저자 사진은 PNG 또는 JPEG, 512 KiB 이하로 선택하세요.');
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }
  return { filename: file.type === 'image/png' ? 'author-photo.png' : 'author-photo.jpg',
    media_type: file.type as 'image/png' | 'image/jpeg', base64: btoa(binary) };
}

function SubmissionAuthorForm({ job, candidate, locked, runAction }: {
  job: ResearchItem; candidate: PortfolioSubmissionCandidate; locked: boolean; runAction: ResearchAction;
}) {
  const [value, setValue] = useState({ author_biography: '', keywords: '', funding_statement: '',
    conflicts_statement: '', cover_letter_note: '' });
  const [photo, setPhoto] = useState<File | null>(null);
  const keywords = value.keywords.split(',').map(word => word.trim()).filter(Boolean);
  const needsPhoto = candidate.venue_id === 'ieee-software';
  const photoProblem = photo && (photo.size > 512 * 1024 || !['image/png', 'image/jpeg'].includes(photo.type));
  const valid = !!candidate.expected_binding && candidate.prepare_available && !!value.author_biography.trim() &&
    keywords.length > 0 && keywords.length <= 10 && !!value.funding_statement.trim() &&
    !!value.conflicts_statement.trim() && (!needsPhoto || !!photo) && !photoProblem;
  const author = job.authorMetadata?.value;
  return <form className="space-y-3" onSubmit={event => {
    event.preventDefault();
    if (!valid || locked || !candidate.expected_binding) return;
    void runAction('submission-prepare', async () => window.paperFactory.preparePortfolioSubmission(job.id, candidate.venue_id, {
      ...candidate.expected_binding!, author_biography: value.author_biography.trim(), keywords,
      photo: await photoInput(photo), funding_statement: value.funding_statement.trim(),
      conflicts_statement: value.conflicts_statement.trim(), cover_letter_note: value.cover_letter_note.trim(),
    }));
  }}>
    <p className="detail-note">현재 저자 정보: {author ? `${author.display_name} · ${author.affiliation} · ${author.email}` : '먼저 실제 저자 정보를 저장하고 저자 정보를 반영해 출력하세요.'}</p>
    <p className="detail-note">키워드와 실제 저자 약력이 들어간 새 제출용 Word·PDF를 만듭니다. 기존 연구·원고·심사와 횟수는 보존됩니다. 아래 정보는 저자가 직접 제공해야 합니다.</p>
    {(['author_biography', 'keywords', 'funding_statement', 'conflicts_statement', 'cover_letter_note'] as const).map(key => {
      const labels = { author_biography: '실제 저자 약력 (영문)', keywords: '키워드 (영문, 쉼표로 구분)',
        funding_statement: '연구비·지원 내역 (영문, 없으면 없다고 명시)',
        conflicts_statement: '이해충돌 선언 (영문, 없으면 없다고 명시)', cover_letter_note: '편집자에게 전할 추가 의견 (영문, 선택)' };
      return <div key={key} className="field"><label htmlFor={`${job.id}-submission-${key}`}>{labels[key]}</label>
        {key === 'keywords' ? <input id={`${job.id}-submission-${key}`} required maxLength={600} value={value[key]} disabled={locked}
          onChange={event => setValue(current => ({ ...current, [key]: event.target.value }))} />
          : <textarea id={`${job.id}-submission-${key}`} required={key !== 'cover_letter_note'} maxLength={4000} value={value[key]}
            disabled={locked} onChange={event => setValue(current => ({ ...current, [key]: event.target.value }))} />}</div>;
    })}
    <div className="field"><label htmlFor={`${job.id}-submission-photo`}>실제 저자 사진{needsPhoto ? ' (IEEE Software 필수)' : ' (선택)'}</label>
      <input id={`${job.id}-submission-photo`} type="file" accept="image/png,image/jpeg" required={needsPhoto} disabled={locked}
        onChange={event => setPhoto(event.currentTarget.files?.[0] ?? null)} />
      <p className="detail-note">PNG·JPEG, 512 KiB 이하. 실제 저자 사진과 사용 권한을 확인하세요.</p>
      {photoProblem && <p role="alert">저자 사진은 PNG·JPEG, 512 KiB 이하로 선택하세요.</p>}
    </div>
    <Button type="submit" variant="outline" disabled={locked || !valid}>키워드·약력 포함한 새 제출 파일 만들기</Button>
  </form>;
}

function SubmissionFileCheck({ job, candidate, preparation, locked, runAction }: {
  job: ResearchItem; candidate: PortfolioSubmissionCandidate; preparation: PortfolioSubmissionPreparation;
  locked: boolean; runAction: ResearchAction;
}) {
  const [qa, setQa] = useState({ word_count: '', docx_pages: '', pdf_pages: '', table_count: '', figure_count: '' });
  const [declarations, setDeclarations] = useState(emptyDeclarations);
  const valid = Object.entries(qa).every(([key, value]) => value !== '' && Number.isSafeInteger(Number(value)) &&
    Number(value) >= (key === 'table_count' || key === 'figure_count' ? 0 : 1)) && Object.values(declarations).every(Boolean);
  return <form className="space-y-3" onSubmit={event => {
    event.preventDefault();
    if (!valid || locked) return;
    void runAction('submission-confirm', () => window.paperFactory.confirmPortfolioSubmission(job.id, {
      preparation_sha256: preparation.sha256,
      expected_docx_sha256: preparation.docx_sha256!,
      expected_pdf_sha256: preparation.pdf_sha256!,
      qa: { word_count: Number(qa.word_count), docx_pages: Number(qa.docx_pages), pdf_pages: Number(qa.pdf_pages),
        table_count: Number(qa.table_count), figure_count: Number(qa.figure_count) }, declarations,
    }));
  }}>
    <p className="detail-note">바로 위의 새 제출용 파일을 직접 열어 확인한 수치를 입력하세요. 이전 원고의 검수와 모델의 추산을 가져오지 않습니다.</p>
    <p className="detail-note">새 Word의 전체 단어 수를 확인하세요. 초록·키워드·참고문헌·저자 약력·표 텍스트를 포함합니다.
      {' '}표·그림 1개당 {candidate.limits.visual_word_cost}단어는 앱이 별도로 더합니다.</p>
    {candidate.venue_id === 'ieee-software' && <p className="detail-note">IEEE Software의 공식 상한 계산은 참고문헌·약력을 제외합니다. 앱은 전체 Word 단어 수에 표·그림 환산을 더해 상한을 보수적으로 점검합니다.</p>}
    <div className="grid gap-3 sm:grid-cols-2">{(Object.keys(qaLabels) as Array<keyof typeof qaLabels>).map(key =>
      <div key={key} className="field"><label htmlFor={`${job.id}-submission-${key}`}>{qaLabels[key]}</label>
        <input id={`${job.id}-submission-${key}`} type="number" required min={key === 'table_count' || key === 'figure_count' ? 0 : 1}
          step={1} max={key === 'word_count' ? 50000 : 200} value={qa[key]} disabled={locked}
          onChange={event => setQa(current => ({ ...current, [key]: event.target.value }))} /></div>)}</div>
    <fieldset className="space-y-3" disabled={locked}><legend className="font-semibold">저자의 최종 확인</legend>
      {(Object.keys(declarationLabels) as Array<keyof typeof declarationLabels>).map(key => <label key={key} className="flex items-start gap-2">
        <input type="checkbox" required checked={declarations[key]}
          onChange={event => setDeclarations(current => ({ ...current, [key]: event.target.checked }))} />
        <span>{declarationLabels[key]}</span>
      </label>)}
    </fieldset>
    <Button type="submit" variant="outline" disabled={locked || !valid}>새 파일 검수·저자 확인 저장하고 투고 패키지 만들기</Button>
  </form>;
}

function SubmissionReceiptForm({ job, preparation, submitted, locked, runAction }: {
  job: ResearchItem; preparation: PortfolioSubmissionPreparation; submitted: boolean; locked: boolean; runAction: ResearchAction;
}) {
  const [value, setValue] = useState({ status: (submitted ? 'withdrawn' : 'submitted') as PortfolioSubmissionRecordInput['status'],
    manuscript_id: '', occurred_at: '', note: '', confirmed: false });
  const valid = !!value.manuscript_id.trim() && !!value.occurred_at && !!value.note.trim() && value.confirmed;
  return <form className="space-y-3" onSubmit={event => {
    event.preventDefault();
    if (!valid || locked) return;
    void runAction('submission-record', () => window.paperFactory.recordPortfolioSubmission(job.id, {
      ...value, preparation_sha256: preparation.sha256, manuscript_id: value.manuscript_id.trim(), note: value.note.trim(),
      occurred_at: new Date(value.occurred_at).toISOString(),
    }));
  }}>
    {submitted && <div className="field"><label htmlFor={`${job.id}-submission-outcome`}>학술지에서 확인한 결과</label>
      <select id={`${job.id}-submission-outcome`} value={value.status} disabled={locked}
        onChange={event => setValue(current => ({ ...current, status: event.target.value as PortfolioSubmissionRecordInput['status'] }))}>
        <option value="withdrawn">철회 완료</option><option value="rejected">불채택 통보</option>
      </select></div>}
    <div className="field"><label htmlFor={`${job.id}-submission-manuscript-id`}>공식 사이트의 원고 접수 번호</label>
      <input id={`${job.id}-submission-manuscript-id`} required maxLength={160} value={value.manuscript_id} disabled={locked}
        onChange={event => setValue(current => ({ ...current, manuscript_id: event.target.value }))} /></div>
    <div className="field"><label htmlFor={`${job.id}-submission-occurred-at`}>{submitted ? '학술지 결과 확인 일시' : '실제 접수 완료 일시'} (현재 시간대)</label>
      <input id={`${job.id}-submission-occurred-at`} type="datetime-local" required value={value.occurred_at} disabled={locked}
        onChange={event => setValue(current => ({ ...current, occurred_at: event.target.value }))} /></div>
    <div className="field"><label htmlFor={`${job.id}-submission-receipt-note`}>접수 화면·공식 이메일에서 확인한 내용</label>
      <textarea id={`${job.id}-submission-receipt-note`} required maxLength={4000} value={value.note} disabled={locked}
        onChange={event => setValue(current => ({ ...current, note: event.target.value }))} /></div>
    <label className="flex items-start gap-2"><input type="checkbox" required checked={value.confirmed} disabled={locked}
      onChange={event => setValue(current => ({ ...current, confirmed: event.target.checked }))} />
      <span>{submitted ? '위 결과가 실제 학술지에서 확인한 내용임을 확인합니다.' : '공식 사이트에서 최종 제출을 완료하고 위 접수 번호와 완료 일시를 확인했습니다.'}</span></label>
    <p className="detail-note">이 기록은 사용자가 확인한 정보입니다. 앱이 학술지의 접수·철회·심사 결과를 외부에서 검증한 것은 아닙니다.</p>
    <Button type="submit" variant="outline" disabled={locked || !valid}>{submitted ? '확인한 학술지 결과 기록' : '실제 접수 완료 정보 기록'}</Button>
  </form>;
}

export function PortfolioSubmission({ job, locked, runAction }: { job: ResearchItem; locked: boolean; runAction: ResearchAction }) {
  const state = job.repositoryPaper?.portfolio?.submission;
  const [selectedVenue, setSelectedVenue] = useState(state?.selected_venue_id ?? '');
  const [replacingPreparation, setReplacingPreparation] = useState(false);
  useEffect(() => {
    if (state?.selected_venue_id) setSelectedVenue(state.selected_venue_id);
  }, [state?.selected_venue_id]);
  useEffect(() => { setReplacingPreparation(false); }, [selectedVenue, state?.preparation?.sha256]);
  if (!state) return null;
  const candidate = state.candidates.find(item => item.venue_id === selectedVenue);
  const preparation = state.preparation;
  const released = state.status === 'withdrawn' || state.status === 'rejected';
  const preparedHere = preparation?.venue_id === selectedVenue && preparation.current &&
    preparation.generation_status === 'completed' && !released && !replacingPreparation;
  const activeSubmission = state.status === 'submitted';
  const localRelease = state.status === 'withdrawn' && !state.portal_record?.manuscript_id;
  return <section className="space-y-4 rounded-base border-2 border-border p-3 text-sm" aria-label="실제 학술지 투고">
    <div className="section-heading"><h5 className="font-semibold">실제 학술지 투고</h5><Badge variant="neutral">{localRelease ? '미제출 준비 해제됨' : statusLabels[state.status]}</Badge></div>
    <p className="detail-note">두 원고는 같은 연구의 대안입니다. 학술지 하나를 선택해 준비하고 공식 사이트에서 제출하세요. 사이트를 여는 것과 앱의 내부 심사 통과는 실제 접수가 아닙니다.</p>
    <fieldset className="space-y-2" disabled={locked || activeSubmission || (!!preparation && !released)}><legend className="font-semibold">1. 학술지 하나 선택 · 실제 저자 정보로 제출 파일 만들기</legend>
      {state.candidates.map(item => <label key={item.venue_id} className="flex items-start gap-2">
        <input type="radio" name={`${job.id}-submission-venue`} value={item.venue_id} checked={selectedVenue === item.venue_id}
          onChange={() => setSelectedVenue(item.venue_id)} /><span>{item.name}</span>
      </label>)}
    </fieldset>
    {preparation && !activeSubmission && !released && <Button variant="ghost" size="sm" disabled={locked}
      onClick={() => void runAction('submission-release', () => window.paperFactory.recordPortfolioSubmission(job.id, {
        preparation_sha256: preparation.sha256, status: 'withdrawn', manuscript_id: '', occurred_at: new Date().toISOString(),
        confirmed: true, note: '사용자가 미제출 투고 준비를 해제했습니다.',
      }))}>미제출 준비 취소하고 학술지 다시 선택</Button>}
    {activeSubmission && preparation && <section className="space-y-3" aria-label="실제 접수 결과 기록">
      <h6 className="font-semibold">공식 사이트에서 확인한 철회·불채택 결과 기록</h6>
      <SubmissionReceiptForm key={`${preparation.sha256}:submitted`} job={job} preparation={preparation}
        submitted locked={locked} runAction={runAction} />
    </section>}
    {activeSubmission && <p className="detail-note">접수 기록이 있는 동안 다른 대안 원고를 준비하지 않습니다. 실제 철회 완료나 불채택을 확인했다면 아래에 결과를 기록하세요.</p>}
    {candidate && <>
      <div className="action-row">
        <Button variant="ghost" size="sm" disabled={locked} onClick={() => void runAction('submission-guidelines', () =>
          window.paperFactory.openPortfolioSubmissionSite(job.id, candidate.venue_id, 'guidelines'))}>{candidate.name} 공식 투고 안내 열기</Button>
        <Button variant="ghost" size="sm" disabled={locked || !candidate.expected_binding} onClick={() => void runAction('submission-portal', () =>
          window.paperFactory.openPortfolioSubmissionSite(job.id, candidate.venue_id, 'portal'))}>공식 사이트의 유형·필수 항목 확인</Button>
      </div>
      <p className="detail-note">확인한 수치 요건: {candidate.requirements_checked_at} · 분량 {candidate.limits.min_words ? `${candidate.limits.min_words}~` : '최대 '}{candidate.limits.max_words}단어 · 초록 최대 {candidate.limits.max_abstract_words}단어 · 참고문헌 최대 {candidate.limits.max_references}개</p>
      {!!candidate.missing.length && <ul className="list-disc space-y-1 pl-5" aria-label="투고 준비에 남은 항목">{candidate.missing.map((item, index) => <li key={index}>{item}</li>)}</ul>}
      {preparation?.venue_id === selectedVenue && preparation.errors.length > 0 && <ul className="list-disc space-y-1 pl-5" aria-label="제출 파일 생성 오류">{preparation.errors.map((item, index) => <li key={index}>{item}</li>)}</ul>}
      {released && <p className="detail-note">기존 접수·결과 기록을 보존했습니다. 다시 투고하려면 새 제출 파일을 만들고 새 파일의 검수와 저자 확인을 진행하세요.</p>}
      {preparedHere && !activeSubmission && <Button variant="ghost" size="sm" disabled={locked || !candidate.prepare_available}
        onClick={() => setReplacingPreparation(true)}>저자·키워드 정보를 고쳐 새 제출 파일 만들기</Button>}
      {replacingPreparation && <Button variant="ghost" size="sm" disabled={locked} onClick={() => setReplacingPreparation(false)}>현재 제출 파일로 돌아가기</Button>}
      {!preparedHere && !activeSubmission && <SubmissionAuthorForm key={`${candidate.venue_id}:${JSON.stringify(candidate.expected_binding)}`}
        job={job} candidate={candidate} locked={locked} runAction={runAction} />}
      {preparedHere && <>
        <section className="space-y-3" aria-label="새 제출 파일 검수">
          <h6 className="font-semibold">2. 키워드·약력이 포함된 새 제출 파일 직접 검수</h6>
          <p className="detail-note">이 파일은 기존 심사를 통과한 본문에 제공한 키워드와 저자 약력을 반영한 제출용 출력입니다. 새 파일 전체 페이지를 확인해야 합니다.</p>
          {([['docx_artifact_id', 'Word'], ['pdf_artifact_id', 'PDF'], ['md_artifact_id', 'Markdown']] as const).map(([key, label]) => <div key={key} className="action-row">
            <span>새 제출용 {label}</span>
            <Button size="sm" variant="outline" disabled={locked} onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, preparation[key]!))}>저장</Button>
            <Button size="sm" variant="ghost" disabled={locked} onClick={() => void runAction('open', () => window.paperFactory.openArtifact(job.id, preparation[key]!))}>열기</Button>
          </div>)}
          {!preparation.confirmation && !activeSubmission && <SubmissionFileCheck key={preparation.sha256} job={job} candidate={candidate}
            preparation={preparation} locked={locked} runAction={runAction} />}
          {preparation.confirmation && <p className="detail-note">보존된 직접 검수: Word {preparation.confirmation.qa.docx_pages}페이지 · PDF {preparation.confirmation.qa.pdf_pages}페이지 · 분량 환산 {preparation.confirmation.metrics.effective_words}단어. 저자 확인과 정확한 파일에 결속된 기록이며 학술지 승인을 뜻하지 않습니다.</p>}
        </section>
        {preparation.package_artifact_id && preparation.confirmation && <>
          <section className="space-y-3" aria-label="투고 패키지와 공식 사이트">
            <h6 className="font-semibold">3. 투고 패키지 저장 · 공식 사이트에서 직접 제출</h6>
            {([['package_artifact_id', '투고 패키지 ZIP'], ['cover_letter_artifact_id', '편집자에게 보내는 투고 서한'], ['metadata_artifact_id', '공식 사이트 입력 정보']] as const).map(([key, label]) =>
              <Button key={key} variant="outline" disabled={locked} onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, preparation[key]!))}>{label} 저장</Button>)}
            <Button variant="outline" disabled={locked || activeSubmission} onClick={() => void runAction('submission-portal', () => window.paperFactory.openPortfolioSubmissionSite(job.id, candidate.venue_id, 'portal'))}>{candidate.name} 공식 투고 사이트 열기</Button>
            <p className="detail-note">IEEE 공식 사이트 계정으로 별도 로그인하세요. 실제 화면에서 해당 일반 Feature Article 유형을 확인하고 파일·저자·선언을 입력한 뒤 최종 제출하세요. 사진·연구비·이해충돌 정보는 패키지와 입력 정보에서 확인할 수 있습니다.</p>
          </section>
          {!activeSubmission && <section className="space-y-3" aria-label="실제 접수 결과 기록">
            <h6 className="font-semibold">4. 공식 사이트의 실제 접수·결과 정보 기록</h6>
            <SubmissionReceiptForm key={`${preparation.sha256}:${state.status}`} job={job} preparation={preparation}
              submitted={activeSubmission} locked={locked} runAction={runAction} />
          </section>}
        </>}
      </>}
    </>}
    {!!state.history.length && <details className="space-y-2"><summary className="font-semibold">보존된 사용자 접수·결과 기록 {state.history.length}개</summary>
      <ul className="mt-2 space-y-3">{state.history.map(record => <li key={record.artifact_id}>
        <p>{record.status === 'withdrawn' && !record.manuscript_id ? '미제출 준비 해제' : statusLabels[record.status]} · {record.manuscript_id} · {record.occurred_at}</p><p className="detail-note whitespace-pre-wrap">{record.note}</p>
      </li>)}</ul>
    </details>}
  </section>;
}
