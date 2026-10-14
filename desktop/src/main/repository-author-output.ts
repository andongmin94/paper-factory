import { isDeepStrictEqual } from 'node:util';
import type { RepositoryPaperProgress, RepositoryPortfolioVenue, ResearchItem } from '../shared/research.js';
import { inspectRepositoryPortfolioOutputs } from '../shared/publication.js';
import { EngineError } from './engine.js';
import { portfolioScience, submissionRecordsPreserved } from './portfolio-submission.js';

type AuthorOutputState = { repository_paper?: RepositoryPaperProgress | null; author_metadata?: ResearchItem['authorMetadata'];
  artifacts: Record<string, { id: string; sha256: string; size: number }> };

function baseOutputIds(venue: RepositoryPortfolioVenue) {
  const prefix = `repository-portfolio-${venue.venue_id}`;
  const selected = venue.layout_export?.status === 'completed' ? venue.layout_export
    : venue.format_export?.status === 'completed' ? venue.format_export : null;
  const suffix = selected === venue.layout_export && selected ? '-layout' : selected ? '-format'
    : venue.export?.artifact_id === `${prefix}-export-repair-${venue.admitted_drafts}` ? '-repair' : '';
  return Object.fromEntries((['pdf', 'docx'] as const).map(format => [format,
    selected?.outputs?.[format]?.artifact_id ?? `${prefix}-${format}${suffix}-${venue.admitted_drafts}`]));
}

function restoreAuthorView(venue: RepositoryPortfolioVenue, prior: RepositoryPortfolioVenue, counts: boolean) {
  const restored = { ...venue, artifact_ids: { ...venue.artifact_ids, pdf: prior.artifact_ids.pdf, docx: prior.artifact_ids.docx } };
  const fields = ['author_export', 'author_export_available', 'author_export_status', ...(counts ? ['author_export_attempts'] : [])] as const;
  for (const field of fields) {
    if (Object.hasOwn(prior, field)) Object.assign(restored, { [field]: prior[field as keyof RepositoryPortfolioVenue] });
    else delete restored[field as keyof typeof restored];
  }
  return restored;
}

/** Metadata can invalidate only its public output selection; it cannot revise science. */
export function verifyPortfolioAuthorMetadataView(previous: AuthorOutputState, updated: AuthorOutputState) {
  const before = previous.repository_paper, after = updated.repository_paper;
  if (!before?.portfolio || !after?.portfolio) return isDeepStrictEqual(before, after);
  const venues = after.portfolio.venues.map((venue, index) => {
    const prior = before.portfolio!.venues[index];
    if (!prior || prior.venue_id !== venue.venue_id) return venue;
    const sameAuthor = previous.author_metadata?.artifact_id === updated.author_metadata?.artifact_id &&
      previous.author_metadata?.sha256 === updated.author_metadata?.sha256;
    const ids = baseOutputIds(prior);
    if (sameAuthor && !isDeepStrictEqual(venue, prior) || !sameAuthor && (
      venue.author_export !== null || !['not_started', 'stale', 'unavailable', 'interrupted'].includes(venue.author_export_status) ||
      typeof venue.author_export_available !== 'boolean' ||
      (venue.author_export_available && (venue.author_export_attempts >= 3 || !venue.draft || !venue.review)) ||
      (['pdf', 'docx'] as const).some(format => venue.artifact_ids[format] !==
        (prior.author_export_status === 'completed' ? ids[format] : prior.artifact_ids[format])))) return venue;
    return restoreAuthorView(venue, prior, false);
  });
  return isDeepStrictEqual(portfolioScience({ ...after, portfolio: { ...after.portfolio, venues } }), portfolioScience(before)) &&
    submissionRecordsPreserved(before, after);
}

/** Permit only the requested byline receipt and output view while retaining every other venue field. */
export function verifyPortfolioAuthorExport(previous: AuthorOutputState, updated: AuthorOutputState, venueId: string) {
  const before = previous.repository_paper, after = updated.repository_paper;
  const prior = before?.portfolio?.venues.find(venue => venue.venue_id === venueId);
  const venue = after?.portfolio?.venues.find(item => item.venue_id === venueId);
  const receipt = venue?.author_export;
  const prefix = `repository-portfolio-${venueId}`;
  const baseExport = prior?.layout_export?.status === 'completed' ? prior.layout_export
    : prior?.format_export?.status === 'completed' ? prior.format_export : prior?.export;
  const baseInputId = baseExport && 'input_artifact_id' in baseExport ? baseExport.input_artifact_id
    : `${prefix}-export-markdown${baseExport?.artifact_id === `${prefix}-export-repair-${prior?.admitted_drafts}` ? '-repair' : ''}-${prior?.admitted_drafts}`;
  const descriptor = (id: string, hash: string) => {
    const artifact = updated.artifacts[id];
    return artifact?.sha256 === hash && /^[a-f0-9]{64}$/.test(hash) && Number.isSafeInteger(artifact.size) && artifact.size > 0;
  };
  if (!prior || !venue || !receipt || !before?.portfolio || !after?.portfolio ||
      !isDeepStrictEqual(previous.author_metadata, updated.author_metadata) ||
      venue.author_export_attempts !== prior.author_export_attempts + 1 || venue.author_export_attempts > 3 ||
      !Number.isSafeInteger(receipt.attempt) || receipt.attempt < 1 || receipt.attempt > 3 ||
      receipt.current !== true || receipt.model_calls !== 0 || receipt.scope !== 'explicit-author-block-only' ||
      receipt.scientific_approval_changed !== false || !descriptor(receipt.artifact_id, receipt.sha256) ||
      !descriptor(receipt.input_artifact_id, receipt.input_sha256) ||
      receipt.artifact_id !== `${prefix}-export-author-${receipt.attempt}-${prior.admitted_drafts}` ||
      receipt.input_artifact_id !== `${prefix}-export-markdown-author-${receipt.attempt}-${prior.admitted_drafts}` ||
      !/^[a-f0-9]{64}$/.test(receipt.author_block_sha256) || !/^[a-f0-9]{64}$/.test(receipt.body_sha256) ||
      receipt.author_artifact_id !== updated.author_metadata?.artifact_id || receipt.author_sha256 !== updated.author_metadata?.sha256 ||
      receipt.bindings?.author_artifact_id !== receipt.author_artifact_id || receipt.bindings?.author_sha256 !== receipt.author_sha256 ||
      receipt.bindings?.venue_id !== venueId || receipt.bindings?.draft_attempt !== prior.admitted_drafts ||
      receipt.draft_sha256 !== prior.draft_sha256 || receipt.markdown_sha256 !== receipt.bindings?.markdown_sha256 ||
      !baseExport || receipt.bindings?.base_export_artifact_id !== baseExport.artifact_id ||
      receipt.bindings?.base_export_sha256 !== baseExport.sha256 || !descriptor(baseExport.artifact_id, baseExport.sha256) ||
      receipt.bindings?.base_input_artifact_id !== baseInputId || !descriptor(baseInputId, receipt.bindings?.base_input_sha256) ||
      receipt.bindings?.draft_artifact_id !== prior.artifact_ids.draft || receipt.bindings?.draft_sha256 !== prior.draft_sha256 ||
      receipt.bindings?.markdown_artifact_id !== prior.artifact_ids.markdown ||
      receipt.bindings?.markdown_sha256 !== previous.artifacts[prior.artifact_ids.markdown!]?.sha256 ||
      receipt.bindings?.review_artifact_id !== prior.artifact_ids.review ||
      receipt.bindings?.review_sha256 !== previous.artifacts[prior.artifact_ids.review!]?.sha256) {
    throw new EngineError('RESEARCH_STATE_INVALID', '저자 출력이 현재 저자·원고·심사·입력·출력 결속과 일치하지 않습니다.');
  }
  for (const [format, output] of Object.entries(receipt.outputs)) {
    if (!['pdf', 'docx'].includes(format) || output.artifact_id !== `${prefix}-${format}-author-${receipt.attempt}-${prior.admitted_drafts}` ||
        !descriptor(output.artifact_id, output.sha256) ||
        output.conversion_artifact_id !== `${prefix}-${format}-conversion-author-${receipt.attempt}-${prior.admitted_drafts}` ||
        !updated.artifacts[output.conversion_artifact_id]) {
      throw new EngineError('RESEARCH_STATE_INVALID', '저자 출력이 현재 원고의 실제 출력·변환 파일과 일치하지 않습니다.');
    }
  }
  const restored = { ...after, portfolio: { ...after.portfolio,
    venues: after.portfolio.venues.map(item => item.venue_id === venueId ? restoreAuthorView(item, prior, true) : item) } };
  const outputs = inspectRepositoryPortfolioOutputs(venue, Object.values(updated.artifacts), updated.author_metadata);
  const completed = receipt.status === 'completed' && venue.author_export_status === 'completed' && !venue.author_export_available &&
    outputs.filter(output => output.format !== 'markdown').length === 2;
  const failed = receipt.status === 'failed' && venue.author_export_status === 'failed' && receipt.errors.length > 0 &&
    isDeepStrictEqual(venue.artifact_ids, prior.artifact_ids) && venue.author_export_available === (venue.author_export_attempts < 3);
  if (!isDeepStrictEqual(portfolioScience(restored), portfolioScience(before)) ||
      !submissionRecordsPreserved(before, after) || !(completed || failed)) {
    throw new EngineError('RESEARCH_STATE_INVALID', '저자 출력이 과학 본문·심사·준비도·기존 출력·다른 매체·횟수를 변경했습니다.');
  }
  return receipt;
}
