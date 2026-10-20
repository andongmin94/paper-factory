import type { RepositoryPaperProgress, RepositoryPortfolioVenue, RepositoryPortfolioFrame, RepositoryPortfolioOutcome, ResearchItem } from './research.js';
import { getPublicationVenue, PUBLICATION_CATALOG, type PublicationCatalog, type PublicationTarget } from './venues.js';

export const NEW_RESEARCH_MODE = 'repository_analysis' as const;

export function repositoryPortfolioReasoningReady(venue: RepositoryPortfolioVenue) {
  return Boolean(venue.analysis_current && venue.review && Object.entries(venue.review.criteria).every(([key, criterion]) =>
    key === 'presentation' || criterion.passed) && venue.review.content_assessment?.comparison.passed &&
    venue.review.content_assessment.contribution.passed);
}

interface Article {
  title: string;
  sections: Array<{ heading: string; text: string }>;
  source_evidence: Array<{ path: string; sha256: string }>;
  literature_evidence: Array<{ source_id: string }>;
  document_evidence: Array<{ source_id: string }>;
}

export interface RepositoryArticleFormat {
  venueId: string | null;
  numericGuidanceVerified: boolean;
  estimatedWords: number;
  maximumWordsEstimate: number;
  abstractWords: number;
  references: number;
  tables: number;
  figures: number;
  insights: number;
  formatReady: boolean;
  blockers: string[];
  uncheckedRequirements: string[];
}

function plainText(text: string) {
  return text.replace(/\{\{(?:source|citation|document):[^{}]+\}\}/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[\d+(?:\s*[,–-]\s*\d+)*\]/g, '')
    .replace(/^\s*(?:```|~~~).*$/gm, '')
    .replace(/<[^>]+>/g, '')
    .replace(/[|]/g, ' ')
    .replace(/[`*#]/g, '');
}

function words(text: string) {
  return plainText(text).split(/\s+/u).filter(word => /[\p{L}\p{N}]/u.test(word)).length;
}

function maximumWords(text: string) {
  return (plainText(text).match(/[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*/gu) ?? []).length;
}

/** Estimate the saved article, separately from scientific and author approval.
 * References match the native renderer's deduplicated bibliography.
 * Software replaces table text with its fixed visual allowance. Whole-article
 * profiles retain table text, references and bios as well as their visual allowance.
 * Whitespace words are a conservative minimum estimate; punctuation-separated
 * words provide the more conservative maximum check. Final Word/PDF counts remain separate.
 */
export function inspectRepositoryArticle(draft: Article, target: Pick<PublicationTarget, 'venue_id' | 'article_category'> | null | undefined, catalog: PublicationCatalog = PUBLICATION_CATALOG, renderedMarkdown?: string): RepositoryArticleFormat {
  const venue = getPublicationVenue(target?.venue_id, catalog.venues);
  const limits = venue?.verified_limits ?? {};
  const wholeArticle = limits.word_count_scope === 'whole_article';
  let tables = 0, figures = 0;
  const excluded = ['References', 'Bibliography', 'Author Biographies', 'Author Information'];
  const source = renderedMarkdown === undefined ? '# ' + draft.title + '\n' + draft.sections
    .filter(section => wholeArticle || !excluded.includes(section.heading))
    .map(section => '## ' + section.heading + '\n' + section.text).join('\n')
    : wholeArticle ? renderedMarkdown : renderedMarkdown.split(/(?=^##\s+)/m)
      .filter(section => !excluded.includes(/^##\s+([^\r\n]+)/.exec(section)?.[1]?.trim() ?? '')).join('');
  const lines = source.split(/\r?\n/), prose: string[] = [];
  let fenced = false;
  for (let index = 0; index < lines.length; index++) {
    if (/^\s*(```|~~~)/.test(lines[index])) fenced = !fenced;
    const cells = (lines[index + 1] ?? '').trim().replace(/^\|/, '').replace(/\|$/, '').split('|');
    const table = !fenced && lines[index].includes('|') && cells.length > 1 &&
      cells.every(cell => /^\s*:?-{3,}:?\s*$/.test(cell));
    if (table) {
      tables++;
      if (wholeArticle || limits.visual_word_cost === undefined) prose.push(lines[index], lines[index + 1]);
      index++;
      while (index + 1 < lines.length && lines[index + 1].trim() && lines[index + 1].includes('|')) {
        index++;
        if (wholeArticle || limits.visual_word_cost === undefined) prose.push(lines[index]);
      }
    } else prose.push(lines[index]);
  }
  const text = prose.join('\n').replace(/!\[([^\]]*)\]\([^)]*\)/g, (_match, caption: string) => {
    figures++;
    return wholeArticle || limits.visual_word_cost === undefined ? caption : '';
  });
  const visualWords = (tables + figures) * (limits.visual_word_cost ?? 0);
  const estimatedWords = words(text) + visualWords;
  const maximumWordsEstimate = maximumWords(text) + visualWords;
  const abstractWords = words(draft.sections.find(section => section.heading === 'Abstract')?.text ?? '');
  const references = new Set(draft.source_evidence.map(item => item.path + ':' + item.sha256)).size +
    new Set(draft.literature_evidence.map(item => item.source_id)).size +
    new Set(draft.document_evidence.map(item => item.source_id)).size;
  const insightsText = draft.sections.find(section => section.heading === 'Actionable Insights')?.text ?? '';
  const insights = (insightsText.match(/^\s*(?:[-*+]\s+|\d+[.)]\s+)\S.+$/gm) ?? []).length;
  const blockers: string[] = [];
  if (!venue || !target) blockers.push('투고처 선택 기록이 없습니다. 학술지와 논문 유형을 먼저 선택해야 합니다.');
  else if (!venue.article_categories.includes(target.article_category)) blockers.push(`${venue.name}의 지원 논문 유형을 선택해야 합니다.`);
  if (limits.min_words !== undefined && estimatedWords < limits.min_words) blockers.push(`최소 분량 추산 ${estimatedWords}단어: ${limits.min_words}단어 이상이 되도록 근거 있는 설명을 보완하고 실제 Word 분량을 확인해야 합니다.`);
  if (limits.max_words !== undefined && maximumWordsEstimate > limits.max_words) blockers.push(`최대 분량 추산 ${maximumWordsEstimate}단어: ${limits.max_words}단어 이하인지 실제 Word에서 확인하고 초과하면 줄여야 합니다.`);
  if (!abstractWords) blockers.push('초록을 작성해야 합니다.');
  else if (limits.max_abstract_words !== undefined && abstractWords > limits.max_abstract_words) blockers.push(`초록 ${abstractWords}단어: ${limits.max_abstract_words}단어 이하로 작성해야 합니다.`);
  if (limits.max_references !== undefined && references > limits.max_references) blockers.push(`참고문헌 ${references}개: ${limits.max_references}개 이하로 정리해야 합니다.`);
  if (limits.insight_count !== undefined && insights !== limits.insight_count) blockers.push(`Actionable Insights에 실천적 시사점 ${limits.insight_count}개를 목록으로 작성해야 합니다.`);
  const numericGuidanceVerified = venue?.requirements_status === 'checked_numeric_guidance';
  const uncheckedRequirements = numericGuidanceVerified
    ? ['확인한 수치는 전체 제출 형식의 승인이 아닙니다. 공식 템플릿 적용, 인용 형식, 저자 필수 자료와 새 Word·PDF의 전체 페이지를 별도로 확인해야 합니다.']
    : ['이 투고처의 최신 분량·초록·참고문헌·제출 형식은 공식 안내에서 최종 확인해야 합니다. 앱의 집필 권장 분량은 공식 제한이 아닙니다.'];
  return { venueId: venue?.id ?? null, numericGuidanceVerified, estimatedWords, maximumWordsEstimate, abstractWords, references, tables, figures, insights,
    formatReady: blockers.length === 0, blockers, uncheckedRequirements };
}

export function inspectRepositoryPortfolioOutputs(venue: RepositoryPortfolioVenue, artifacts: ResearchItem['artifacts'], author: ResearchItem['authorMetadata'] = null) {
  const retained = new Map(artifacts.map(artifact => [artifact.id, artifact]));
  const prefix = `repository-portfolio-${venue.venue_id}`;
  const draftId = `${prefix}-draft-${venue.admitted_drafts}`;
  const draft = retained.get(draftId);
  if (!venue.draft || venue.artifact_ids.draft !== draftId || !draft || draft.sha256 !== venue.draft_sha256 ||
    !/^[a-f0-9]{64}$/.test(draft.sha256) || !Number.isSafeInteger(draft.size) || draft.size <= 0) return [];
  const repairReceipt = venue.export_repair_attempts === 1 && venue.export?.artifact_id === `${prefix}-export-repair-${venue.admitted_drafts}`
    ? retained.get(venue.export.artifact_id) : undefined;
  const repaired = repairReceipt && repairReceipt.sha256 === venue.export?.sha256 &&
    /^[a-f0-9]{64}$/.test(repairReceipt.sha256) && Number.isSafeInteger(repairReceipt.size) && repairReceipt.size > 0;
  const correction = venue.layout_export?.status === 'completed' ? { kind: 'layout', attempts: venue.layout_export_attempts, receipt: venue.layout_export }
    : venue.format_export?.status === 'completed' ? { kind: 'format', attempts: venue.format_export_attempts, receipt: venue.format_export } : null;
  const correctionReceipt = correction && retained.get(correction.receipt.artifact_id);
  const correctionInput = correction && retained.get(correction.receipt.input_artifact_id);
  const corrected = correction && correction.attempts === 1 &&
    correction.receipt.artifact_id === `${prefix}-export-${correction.kind}-${venue.admitted_drafts}` &&
    correctionReceipt?.sha256 === correction.receipt.sha256 && /^[a-f0-9]{64}$/.test(correction.receipt.sha256) &&
    Number.isSafeInteger(correctionReceipt.size) && correctionReceipt.size > 0 &&
    correction.receipt.original_draft_sha256 === venue.draft_sha256 &&
    correctionInput?.sha256 === correction.receipt.input_sha256 && /^[a-f0-9]{64}$/.test(correction.receipt.input_sha256) &&
    Number.isSafeInteger(correctionInput.size) && correctionInput.size > 0;
  const authorExport = venue.author_export;
  const descriptor = (id: string | null | undefined, expectedSha?: string | null) => {
    const artifact = id ? retained.get(id) : undefined;
    return !!artifact && /^[a-f0-9]{64}$/.test(artifact.sha256) && Number.isSafeInteger(artifact.size) && artifact.size > 0 &&
      (expectedSha === undefined || artifact.sha256 === expectedSha);
  };
  const baseExport = correction?.receipt ?? venue.export;
  const baseInputId = correction?.receipt.input_artifact_id ?? `${prefix}-export-markdown${repaired ? '-repair' : ''}-${venue.admitted_drafts}`;
  const authorBinding = authorExport?.bindings;
  const authorCurrent = !!author && author.origin === 'explicit_human_author_metadata' &&
    !!author.value.display_name?.trim() && !!author.value.email?.trim() && !!author.value.affiliation?.trim() &&
    descriptor(author.artifact_id, author.sha256) && !!author.sha256 &&
    !!authorExport && authorExport.current === true && authorExport.status === 'completed' &&
    venue.author_export_status === 'completed' && Number.isSafeInteger(authorExport.attempt) &&
    authorExport.attempt >= 1 && authorExport.attempt <= 3 && authorExport.attempt <= venue.author_export_attempts && venue.author_export_attempts <= 3 &&
    authorExport.model_calls === 0 && authorExport.scope === 'explicit-author-block-only' && authorExport.scientific_approval_changed === false &&
    authorExport.errors.length === 0 && descriptor(authorExport.artifact_id, authorExport.sha256) &&
    authorExport.artifact_id === `${prefix}-export-author-${authorExport.attempt}-${venue.admitted_drafts}` &&
    authorExport.input_artifact_id === `${prefix}-export-markdown-author-${authorExport.attempt}-${venue.admitted_drafts}` &&
    descriptor(authorExport.input_artifact_id, authorExport.input_sha256) &&
    /^[a-f0-9]{64}$/.test(authorExport.author_block_sha256) && /^[a-f0-9]{64}$/.test(authorExport.body_sha256) &&
    authorExport.author_artifact_id === author.artifact_id && authorExport.author_sha256 === author.sha256 &&
    authorBinding?.venue_id === venue.venue_id && authorBinding.draft_attempt === venue.admitted_drafts &&
    authorBinding.draft_artifact_id === venue.artifact_ids.draft && authorBinding.draft_sha256 === venue.draft_sha256 &&
    authorExport.draft_sha256 === authorBinding.draft_sha256 && authorExport.markdown_sha256 === authorBinding.markdown_sha256 &&
    authorBinding.markdown_artifact_id === venue.artifact_ids.markdown && descriptor(authorBinding.markdown_artifact_id, authorBinding.markdown_sha256) &&
    authorBinding.review_artifact_id === venue.artifact_ids.review && descriptor(authorBinding.review_artifact_id, authorBinding.review_sha256) &&
    authorBinding.author_artifact_id === author.artifact_id && authorBinding.author_sha256 === author.sha256 &&
    !!baseExport && authorBinding.base_export_artifact_id === baseExport.artifact_id &&
    authorBinding.base_export_sha256 === baseExport.sha256 && descriptor(baseExport.artifact_id, baseExport.sha256) &&
    authorBinding.base_input_artifact_id === baseInputId && descriptor(baseInputId, authorBinding.base_input_sha256);
  return (['markdown', 'pdf', 'docx'] as const).flatMap(format => {
    const id = format === 'markdown' && authorCurrent ? authorExport!.input_artifact_id : venue.artifact_ids[format];
    const artifact = id ? retained.get(id) : undefined;
    const currentId = format === 'markdown' && authorCurrent && id === authorExport!.input_artifact_id ||
      id === `${prefix}-${format}-${venue.admitted_drafts}` ||
      format !== 'markdown' && (repaired && id === `${prefix}-${format}-repair-${venue.admitted_drafts}` ||
        corrected && id === `${prefix}-${format}-${correction!.kind}-${venue.admitted_drafts}` &&
          correction!.receipt.outputs?.[format]?.artifact_id === id && correction!.receipt.outputs?.[format]?.sha256 === artifact?.sha256 ||
        authorCurrent && id === `${prefix}-${format}-author-${authorExport!.attempt}-${venue.admitted_drafts}` &&
          authorExport!.outputs[format]?.artifact_id === id && descriptor(id, authorExport!.outputs[format]?.sha256) &&
          authorExport!.outputs[format]?.conversion_artifact_id === `${prefix}-${format}-conversion-author-${authorExport!.attempt}-${venue.admitted_drafts}` &&
          descriptor(authorExport!.outputs[format]?.conversion_artifact_id));
    return currentId && artifact &&
      /^[a-f0-9]{64}$/.test(artifact.sha256) && Number.isSafeInteger(artifact.size) && artifact.size > 0
      ? [{ format, artifact }] : [];
  });
}

type PortfolioWork = { action: 'start' | 'analysis' | 'repair_analysis' | 'revise_analysis' | 'collect_literature' | 'collect_documentation' | 'draft' | 'repair' | 'review' | 'revision' | 'export' | 'repair_export' | null; reason: string };
function retainedPortfolioRequestAvailable(binding: RepositoryPortfolioFrame | null, outcome: RepositoryPortfolioOutcome, unsentRequestAvailable: boolean, limit = 3) {
  return !!binding && binding.attempt >= 1 && binding.attempt <= limit && (outcome === null || outcome === 'completed' || outcome === 'started' && unsentRequestAvailable);
}

/** Choose only a supported task; a failed reservation cannot become a fresh model request. */
export function inspectRepositoryPortfolioVenueWork(venue: RepositoryPortfolioVenue, unsentRequestAvailable = false): PortfolioWork {
  if (venue.revision_feedback_pending) {
    return venue.revision_feedback && venue.writer_binding?.revision_feedback_sha256 === venue.revision_feedback.sha256 &&
      retainedPortfolioRequestAvailable(venue.writer_binding, venue.writer_outcome, unsentRequestAvailable)
      ? { action: 'revision', reason: '이 투고본의 보존된 보완 의견을 반영한 새 원고·출력·독립 심사를 진행합니다. 이전 원고·심사와 횟수는 유지합니다.' }
      : { action: null, reason: '보완 의견에 결속된 작성이 실패·중단되었거나 남은 횟수가 없습니다. 원 의견·원고·심사를 보존하며 같은 요청을 다시 보내지 않습니다.' };
  }
  const repair = venue.repair_binding;
  if (venue.repair_attempts <= 1 && repair?.phase === 'venue-manuscript-repair' && repair.repair &&
      retainedPortfolioRequestAvailable(repair, venue.repair_outcome, unsentRequestAvailable, 1)) {
    return { action: 'repair', reason: '완성된 본문을 보존하고 끊긴 작성 응답의 꼬리만 1회 복구하거나 보존된 완료 복구 응답을 제출합니다. 원래 작성 실패와 횟수는 유지합니다.' };
  }
  if (repair || !venue.draft && venue.repair_attempts > 0) return { action: null,
    reason: '꼬리 복구가 실패·중단되었거나 전송 결과가 불확실합니다. 학술지별 복구 1회 한도와 원래 작성 실패 기록을 보존하며 같은 입력을 다시 호출하지 않습니다.' };
  if (!venue.draft) {
    return retainedPortfolioRequestAvailable(venue.writer_binding, venue.writer_outcome, unsentRequestAvailable)
      ? { action: 'draft', reason: '이 학술지의 실제 원고를 작성하거나 보존된 완료 응답을 제출합니다.' }
      : { action: null, reason: '이 학술지의 작성 요청이 실패·중단되었거나 작성 횟수를 모두 사용했습니다. 같은 입력을 다시 호출하지 않습니다.' };
  }
  if (venue.export_repair_available && venue.export_repair_attempts === 0 &&
      (venue.export_status === 'failed' || venue.export_status === 'interrupted')) {
    return { action: 'repair_export', reason: '네이티브에서 확인한 출력 문제를 1회 복구합니다. 모델 호출 없이 보존된 원고의 PDF·Word만 변환하며 원래 출력 실패와 연구 횟수를 유지합니다.' };
  }
  if (venue.export_status === 'not_started' && (!venue.artifact_ids.pdf || !venue.artifact_ids.docx)) {
    return { action: 'export', reason: '독립 심사 전에 현재 원고의 PDF·Word를 변환하고 형식을 선점검합니다.' };
  }
  if (venue.export_status === 'completed' && venue.analysis_current && !venue.review &&
      retainedPortfolioRequestAvailable(venue.reviewer_binding, venue.reviewer_outcome, unsentRequestAvailable)) {
    return { action: 'review', reason: '선점검한 현재 원고의 독립 심사를 진행하거나 보존된 완료 응답을 제출합니다.' };
  }
  if (venue.revise_available && venue.review &&
      retainedPortfolioRequestAvailable(venue.writer_binding, venue.writer_outcome, unsentRequestAvailable)) {
    return { action: 'revision', reason: venue.revise_reason };
  }
  if (!venue.analysis_current) return { action: null, reason: venue.revise_reason };
  if (venue.export_status === 'failed' || venue.export_status === 'interrupted') {
    return { action: null, reason: venue.export_repair_attempts > 0
      ? '출력 복구 1회 한도를 사용했습니다. 원래 변환 실패와 복구 실패·중단 기록을 보존하며 같은 변환을 다시 실행하지 않습니다.'
      : '출력 변환 실패·중단 기록을 보존했습니다. 확인된 복구 조건이 없어 같은 출력 변환을 다시 실행하지 않습니다.' };
  }
  if (!venue.review) return { action: null, reason: '이 원고의 심사 요청이 실패·중단되었거나 심사 횟수를 모두 사용했습니다. 같은 입력을 다시 호출하지 않습니다.' };
  if (!venue.scientific_ready || !venue.content_ready) return { action: null, reason: venue.revise_reason };
  return { action: null, reason: '현재 원고·독립 심사·출력 작업을 완료했습니다. 저자 승인과 제출 요건 확인은 별도로 필요합니다.' };
}

export function inspectRepositoryPortfolioWork(paper: RepositoryPaperProgress, unsentRequestAvailable = false): PortfolioWork {
  if (!paper.plan) {
    return { action: null, reason: '저장소와 두 IEEE 매체의 적합성을 평가한 설계를 먼저 보존해야 합니다.' };
  }
  const portfolio = paper.portfolio;
  if (!portfolio) return { action: 'start', reason: '보존된 설계에서 문헌 확보·공통 분석·적합한 IEEE 매체별 집필을 시작합니다.' };
  if (!portfolio.guidance) return { action: null, reason: '공식 안내 확보가 중단됐습니다. 기존 수집 기록을 덮어쓰거나 다시 요청하지 않습니다.' };
  if (!portfolio.analysis) {
    if (portfolio.literature_collections.some(item => item.status === 'interrupted')) {
      return { action: null, reason: '공통 문헌 확보가 중단됐습니다. 같은 수집을 반복하지 않습니다.' };
    }
    const repair = portfolio.analysis_repair;
    if (repair) {
      return repair.status === 'planned' && portfolio.analysis_binding?.analysis_schema_repair_sha256 === repair.sha256 &&
        retainedPortfolioRequestAvailable(portfolio.analysis_binding, portfolio.analysis_outcome, unsentRequestAvailable) &&
        (paper.analysis_attempts < 3 || portfolio.analysis_outcome !== null)
        ? { action: 'analysis', reason: '보존된 원 응답과 네이티브 검증 오류에 결속된 분석 형식 보완을 1회 수행하거나 완료 보완 응답을 제출합니다. 원래 분석·실패·횟수는 유지합니다.' }
        : { action: null, reason: '분석 형식 보완 1회 기록을 보존했습니다. 실패·중단·미완료 보완을 다시 요청하지 않습니다.' };
    }
    if (portfolio.analysis_repair_available && portfolio.analysis_repair_candidate_artifact_id &&
        portfolio.analysis_outcome === 'completed' && paper.analysis_attempts < 3) {
      return { action: 'repair_analysis', reason: '완료된 첫 분석에서 근거 연결 오류를 확인했습니다. 원 응답·검증 오류를 보존하고 남은 분석 예산에서 형식 보완을 1회 준비합니다.' };
    }
    return retainedPortfolioRequestAvailable(portfolio.analysis_binding, portfolio.analysis_outcome, unsentRequestAvailable) &&
      (paper.analysis_attempts < 3 || portfolio.analysis_outcome !== null)
      ? { action: 'analysis', reason: '공통 보강 분석을 진행하거나 보존된 완료 분석을 제출합니다.' }
      : { action: null, reason: '공통 분석 요청이 실패·중단되었거나 분석 횟수를 모두 사용했습니다. 같은 입력을 다시 호출하지 않습니다.' };
  }
  const work = portfolio.venues.map(venue => inspectRepositoryPortfolioVenueWork(venue, unsentRequestAvailable));
  const pending = work.find(item => item.action !== null && item.action !== 'revision' && item.action !== 'draft');
  if (pending) return pending;
  if (portfolio.all_content_ready) return { action: null,
    reason: '두 IEEE 매체의 실제 원고 평가를 완료했습니다. 추가 자동 보완 없이 저자 승인과 남은 제출 요건을 확인하세요.' };
  if (portfolio.documentation_followup_available) {
    return { action: 'collect_documentation', reason: '실제 심사가 요구한 공식 기술 문서를 남은 수집 한도에서 확보합니다. 원문과 조회 결과를 보존하고 수정 원고의 비교 근거로 결속합니다.' };
  }
  if (portfolio.literature_followup_available && portfolio.literature_budget.used < portfolio.literature_budget.limit) {
    return { action: 'collect_literature', reason: '보존된 실제 심사의 새 질문으로 가까운 원문 문헌을 추가 확보합니다. 기존 자료와 횟수를 유지하고 새 근거를 학술지별 재작성·독립 심사에 결속합니다.' };
  }
  const draft = work.find(item => item.action === 'draft');
  if (draft) return draft;
  const localRevision = work.find(item => item.action === 'revision');
  if (localRevision) return localRevision;
  const revision = portfolio.analysis_revision;
  if (revision?.status === 'planned') {
    return portfolio.analysis_binding?.analysis_revision_sha256 === revision.sha256 &&
      retainedPortfolioRequestAvailable(portfolio.analysis_binding, portfolio.analysis_outcome, unsentRequestAvailable) &&
      (paper.analysis_attempts < 3 || portfolio.analysis_outcome !== null)
      ? { action: 'analysis', reason: '보존된 실제 심사와 보완 계획에 결속된 공통 분석을 남은 예산 안에서 1회 수행하거나 보존된 완료 응답을 제출합니다.' }
      : { action: null, reason: '공통 연구 보완 요청이 실패·중단되었거나 전송 결과가 불확실합니다. 남은 분석 예산과 기존 기록을 보존하며 같은 요청을 반복하지 않습니다.' };
  }
  if (!revision && portfolio.analysis_revision_available && paper.analysis_attempts < 3) {
    return { action: 'revise_analysis', reason: '실제 독립 심사가 요구한 공통 연구 보완 계획을 보존합니다. 기존 분석·원고·심사와 횟수를 유지합니다.' };
  }
  if (revision?.status === 'incomplete') return { action: null,
    reason: '공통 연구 보완 기록은 미완료입니다. 미이행 문헌·비교 소스·사람 검증을 확인하세요. 같은 분석이나 원고 일괄 재작성을 자동 반복하지 않습니다.' };
  if (portfolio.analysis_revision_required) return { action: null,
    reason: '실제 심사가 요구한 공통 연구 보완이 남아 있습니다. 이미 보존한 보완 계획·분석 예산과 미이행 근거를 확인하세요. 분석 완료만으로 학술지별 기여가 충족되지는 않습니다.' };
  return { action: null, reason: '자동으로 진행할 다음 작업이 없습니다. 학술지별 추가 근거·남은 횟수·출력 실패 진단을 확인하세요.' };
}

export interface RepositoryPublicationStatus {
  stage: 'target_pending' | 'draft_pending' | 'review_pending' | 'content_revision' | 'editorial_revision' | 'output_pending' |
    'author_output_pending' | 'author_review_pending' | 'human_hold';
  label: string;
  blockers: string[];
  nextAction: string;
  currentOutputIds: string[];
  previousOutputIds: string[];
  outputCurrent: boolean;
  authorOutputCurrent: boolean;
  formattingRemaining: number;
}

type PublicationJob = Pick<ResearchItem, 'repositoryPaper' | 'artifacts' | 'authorMetadata' | 'draftAttempt'>;
type RepositoryOutputs = Pick<RepositoryPublicationStatus,
  'currentOutputIds' | 'previousOutputIds' | 'outputCurrent' | 'authorOutputCurrent' | 'formattingRemaining'> & {
    latestReceipt: NonNullable<RepositoryPaperProgress['formatting_receipts']>[number] | undefined;
    authorIdentity: boolean;
  };

/** Resolve output identities separately from article quality and the next task. */
function inspectRepositoryOutputs(job: PublicationJob): RepositoryOutputs {
  const paper = job.repositoryPaper;
  const artifacts = new Map(job.artifacts.map(item => [item.id, item]));
  const descriptor = (id: string | undefined | null, expectedSha?: string | null) => {
    const item = id ? artifacts.get(id) : undefined;
    return !!item && /^[a-f0-9]{64}$/.test(item.sha256) && Number.isSafeInteger(item.size) && item.size > 0 &&
      (expectedSha === undefined || item.sha256 === expectedSha);
  };
  const attempts = (paper?.formatting_receipts ?? []).filter(item => item.draft_attempt === job.draftAttempt)
    .sort((left, right) => right.attempt - left.attempt);
  const formattingRemaining = Math.max(0, 3 - new Set(attempts.map(item => item.attempt)).size);
  const latest = attempts[0];
  const draftId = paper?.artifact_ids.draft;
  const markdownId = paper?.artifact_ids.draft_markdown;
  const reviewId = paper?.artifact_ids.review;
  const originalCurrent = !!paper?.draft && draftId === `repository-draft-${job.draftAttempt}` &&
    markdownId === `repository-draft-md-${job.draftAttempt}` && typeof paper.draft_sha256 === 'string' &&
    /^[a-f0-9]{64}$/.test(paper.draft_sha256) && descriptor(draftId, paper.draft_sha256) && descriptor(markdownId);
  const reviewSha = reviewId ? artifacts.get(reviewId)?.sha256 : null;
  const author = job.authorMetadata;
  const authorIdentity = !author || (author.origin === 'explicit_human_author_metadata' &&
    typeof author.sha256 === 'string' && /^[a-f0-9]{64}$/.test(author.sha256) &&
    descriptor(author.artifact_id, author.sha256) && !!author.value.display_name?.trim() &&
    !!author.value.email?.trim() && !!author.value.affiliation?.trim());
  let currentOutputIds: string[] = [];
  let outputCurrent = false;
  let authorOutputCurrent = false;
  if (originalCurrent && latest) {
    const expectedReceiptId = latest.status === 'completed'
      ? `repository-draft-format-${job.draftAttempt}-format-${latest.attempt}`
      : `repository-draft-format-intent-${job.draftAttempt}-format-${latest.attempt}`;
    const manuscriptCurrent = latest.markdown_sha256 === artifacts.get(markdownId!)!.sha256 &&
      latest.draft_sha256 === paper!.draft_sha256 && latest.review_sha256 === reviewSha;
    const reviewCurrent = !paper!.review ? !reviewId
      : reviewId === `repository-review-${job.draftAttempt}` && descriptor(reviewId);
    const inputCurrent = latest.input_artifact_id === `repository-draft-md-${job.draftAttempt}-format-${latest.attempt}` &&
      typeof latest.input_sha256 === 'string' && descriptor(latest.input_artifact_id, latest.input_sha256);
    const authorCurrent = latest.author_artifact_id == null && latest.author_sha256 == null ||
      !!author && authorIdentity && latest.author_artifact_id === author.artifact_id && latest.author_sha256 === author.sha256;
    const currentReceipt = latest.artifact_id === expectedReceiptId && descriptor(latest.artifact_id) &&
      latest.status === 'completed' &&
      manuscriptCurrent && reviewCurrent && inputCurrent && authorCurrent;
    if (currentReceipt) {
      currentOutputIds = ['pdf', 'docx'].flatMap(extension => {
        const output = latest.outputs[extension];
        const expectedId = `repository-draft-${extension}-${job.draftAttempt}-format-${latest.attempt}`;
        return output?.artifact_id === expectedId && paper!.artifact_ids[extension] === output.artifact_id &&
          descriptor(output.artifact_id, output.sha256) &&
          output.conversion_artifact_id === expectedId + '-conversion' && descriptor(output.conversion_artifact_id)
          ? [output.artifact_id] : [];
      });
      outputCurrent = currentOutputIds.length === 2 && latest.errors.length === 0;
      authorOutputCurrent = outputCurrent && !!author && authorIdentity &&
        latest.author_artifact_id === author.artifact_id && latest.author_sha256 === author.sha256;
    }
  } else if (originalCurrent) {
    currentOutputIds = ['pdf', 'docx'].flatMap(extension => {
      const id = paper!.artifact_ids[extension];
      return id === `repository-draft-${extension}-${job.draftAttempt}` && descriptor(id) ? [id] : [];
    });
    outputCurrent = currentOutputIds.length === 2 && !(paper!.conversion_errors?.length);
  }
  const previousOutputIds = job.artifacts.filter(item =>
    /^repository-draft-(?:pdf|docx)-[1-3](?:-format-[1-3])?$/.test(item.id) && !currentOutputIds.includes(item.id)).map(item => item.id);
  return { currentOutputIds, previousOutputIds, outputCurrent, authorOutputCurrent, formattingRemaining,
    latestReceipt: latest, authorIdentity };
}

/** Derive the next task without changing native assessments or approving submission. */
export function inspectRepositoryPublication(job: PublicationJob): RepositoryPublicationStatus {
  const paper = job.repositoryPaper;
  const { latestReceipt: latest, authorIdentity, ...outputs } = inspectRepositoryOutputs(job);
  const { outputCurrent, authorOutputCurrent, formattingRemaining } = outputs;
  const author = job.authorMetadata;
  const state = (stage: RepositoryPublicationStatus['stage'], label: string, blockers: string[], nextAction: string): RepositoryPublicationStatus => ({
    stage, label, blockers: [...new Set(blockers)], nextAction, ...outputs,
  });
  const target = paper?.plan?.publication_target;
  const venue = getPublicationVenue(target?.venue_id, paper?.publication_venues?.venues);
  if (!paper?.draft) return state('draft_pending', '원고 작성 대기', ['아직 실제 원고가 없습니다.'],
    '저장소를 분석하고 적합한 IEEE Software·Security & Privacy Feature Article을 작성하세요.');
  if (!target || !venue) return state('target_pending', '투고처 선택 기록 없음', ['보존된 원고에 학술지 선택 근거가 없습니다.'],
    '이 원고의 투고처 적합성과 논문 유형을 직접 확인하세요. 과거 기록에 선택 결과를 추정해 넣지 않습니다.');
  const format = inspectRepositoryArticle(paper.draft, target, paper.publication_venues ?? PUBLICATION_CATALOG);
  const editorial = () => state('editorial_revision', '투고처 형식 보완 필요', format.blockers,
    job.draftAttempt !== null && job.draftAttempt >= 3
      ? '원고 3회 한도에 도달했습니다. 현재 원고의 투고처 형식 문제와 보존된 근거를 확인하세요.'
      : `${venue.name}의 확인한 요건과 위의 구체적 문제를 반영한 새 원고를 작성하세요.`);
  if (!paper.review && !format.formatReady) return editorial();
  if (!paper.review) return state('review_pending', '독립 심사 대기', ['현재 원고의 독립 심사가 없습니다.'],
    `현재 원고의 실제 분석·비교·기여와 ${venue.name} 적합성을 독립 심사하세요.`);
  const held = paper.next_actions.filter(action => action.action === 'human_validation' || action.action === 'infeasible');
  if (held.length) return state('human_hold', '직접 확인 또는 중단 필요', held.map(action => action.required_change),
    held.map(action => `${action.target}: ${action.required_change} 확인 방법: ${action.verification}`).join(' '));
  const failedCriteria = Object.values(paper.review.criteria).filter(item => !item.passed).map(item => item.reason);
  const assessment = paper.content_assessment ?? paper.review.content_assessment;
  const scienceReady = paper.scientific_ready && !failedCriteria.length && !paper.review.issues.length;
  const contentReady = paper.content_ready === true && !!assessment && assessment.comparison.passed &&
    assessment.contribution.passed && !assessment.issues.length;
  if (!scienceReady || !contentReady || paper.revision_feedback) return state('content_revision', '내용 보완 필요', [
    ...failedCriteria, ...paper.review.issues, ...(assessment?.issues ?? []),
    ...(!paper.scientific_ready && !failedCriteria.length && !paper.review.issues.length
      ? ['보존된 과학 심사의 통과 상태가 확인되지 않았습니다.'] : []),
    ...(paper.content_ready !== true ? ['보존된 비교·기여 내용 평가의 통과 상태가 확인되지 않았습니다.'] : []),
    ...(!assessment ? ['현재 원고의 비교·기여 내용 평가가 없습니다.'] : []),
    ...(assessment && !assessment.comparison.passed ? [assessment.comparison.reason] : []),
    ...(assessment && !assessment.contribution.passed ? [assessment.contribution.reason] : []),
    ...(paper.revision_feedback?.issues ?? []),
  ], job.draftAttempt !== null && job.draftAttempt >= 3
    ? '보존된 원고·심사에서 해결되지 않은 요구를 확인하세요. 원고 3회 한도에 도달했습니다.'
    : '보존된 구체적 요구를 실제 분석과 원고에 반영한 새 원고를 작성하고 독립 심사하세요.');
  if (!format.formatReady) return editorial();
  if (author && (!outputCurrent || !authorOutputCurrent)) return state('author_output_pending', '저자 정보 반영 출력 필요', [
    '현재 원고·심사·실제 저자 정보에 결속된 PDF와 Word 출력이 모두 확인되지 않았습니다.',
    ...(!authorIdentity ? ['실제 저자 이름·소속·연락처와 보존된 저자 정보의 결속을 먼저 확인해야 합니다.'] : []),
    ...(latest?.errors.map(error => `${error.format}: ${error.message}`) ?? []),
  ], !authorIdentity ? '실제 저자 이름·소속·연락처를 올바르게 입력·보존한 뒤 출력 다시 생성을 진행하세요.'
    : formattingRemaining ? '출력 다시 생성으로 현재 저자 정보를 반영하세요. 원고와 심사 횟수는 늘리지 않습니다.'
    : '출력 보완 3회 한도에 도달했습니다. 보존된 출력 오류와 이전 파일을 확인하세요.');
  if (!outputCurrent) return state('output_pending', '출력 생성 필요', [
    '현재 원고의 PDF와 Word 출력이 모두 확인되지 않았습니다.',
    ...(latest?.errors.map(error => `${error.format}: ${error.message}`) ?? paper.conversion_errors?.map(error => `${error.format}: ${error.message}`) ?? []),
  ], formattingRemaining ? '현재 원고의 PDF와 Word를 출력 다시 생성으로 완성하세요.'
    : '출력 보완 3회 한도에 도달했습니다. 보존된 출력 오류와 이전 파일을 확인하세요.');
  return state('author_review_pending', '저자 최종 확인 필요', [
    ...format.uncheckedRequirements,
    ...(!author ? ['실제 저자 이름·소속·연락처가 아직 입력되지 않았습니다.'] : []),
    '저자의 해석·AI 사용 공시·저작권과 선언, 필요한 저자 소개·사진 및 모든 PDF 페이지의 직접 확인이 남았습니다.',
  ], `실제 저자 정보를 확인하고 해석·AI 사용 공시·권리와 선언·필요한 저자 소개와 사진·PDF 모든 페이지를 직접 검토한 뒤 ${venue.name} 공식 투고 요건을 최종 확인하세요.`);
}
