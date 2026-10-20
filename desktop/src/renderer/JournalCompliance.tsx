import type { JournalComplianceReport } from '../shared/manuscript-improvement';

const itemLabels: Record<string, string> = {
  abstract: '초록 분량', abstract_structure: '초록 구성', reference_count: '참고문헌 개수·번호',
  reference_metadata: '참고문헌 서지정보', keywords: '키워드', self_attestation: '본문의 근거 없는 규정 충족 주장',
  escaped_prose: '본문 문단 구분', placeholders: '미완성 표시·근거 토큰', ai_disclosure: 'AI 사용 공시',
  word_count: '분량', actionable_insights: '실무 적용 요점', author_identity: '저자 정보 확인',
  author_biography: '실제 저자 약력', author_declarations: '저자 동의·권리 확인', author_photo: '실제 저자 사진',
  native_word: '공식 Word 양식', all_pages: 'PDF 전체 페이지 구조 검사',
  export_binding: '원고·공식 양식·출력 파일 일치', visual_review: '전체 페이지 직접 확인',
};

export function JournalCompliance({ report }: { report: JournalComplianceReport }) {
  const labels = { passed: '충족', failed: '보완 필요', pending: '확인 대기' };
  const native = report.metrics.native_word;
  return <section className="space-y-2" aria-label="투고 형식과 제출 요건">
    <h6 className="font-semibold">투고 형식·제출 요건</h6>
    <p className="detail-note">본문·수치 검사: {report.content_format_passed ? '충족' : '보완 필요'} · 제출 전 확인 {report.pending.length}개</p>
    {native && <p className="detail-note">실제 Word 측정: 전체 {native.whole_words}단어 · 본문 {native.body_words}단어 · 초록 {native.abstract_words}단어 · 참고문헌 {native.reference_count}개
      {report.metrics.effective_words !== undefined && ` · 분량 환산 ${report.metrics.effective_words}단어`}</p>}
    {report.page_qa && <p className="detail-note">실제 PDF 전체 {report.page_qa.page_count}페이지 생성·구조 검사: {report.page_qa.automatic_checks ? '충족' : '보완 필요'} · 직접 육안 확인은 별도입니다.</p>}
    <p className="detail-note">저자 정보·사진·동의와 전체 페이지 직접 확인은 아래 상태로 확인하세요. 원고 품질 점수와 별도로 기록합니다.</p>
    <ul className="space-y-2">{report.items.map(item => <li key={item.id}>
      <p className="font-semibold">{itemLabels[item.id] ?? item.label} · {labels[item.status]}</p><p>{item.reason}</p>
      {item.source_url?.startsWith('https://') && <a href={item.source_url} target="_blank" rel="noreferrer" className="detail-note underline">공식 기준</a>}
    </li>)}</ul>
  </section>;
}
