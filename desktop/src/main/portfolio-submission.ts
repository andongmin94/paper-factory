import { isDeepStrictEqual } from 'node:util';
import type { RepositoryPaperProgress, ResearchItem } from '../shared/research.js';
import type { PortfolioSubmissionPreparation } from '../shared/submission.js';
import { EngineError } from './engine.js';

const sites: Record<string, { portal: string; guidelines: string }> = {
  'ieee-software': {
    portal: 'https://ieee.atyponrex.com/journal/sw-cs',
    guidelines: 'https://www.computer.org/digital-library/magazines/so/cfp-ieee-software',
  },
  'ieee-security-privacy': {
    portal: 'https://ieee.atyponrex.com/journal/sp-cs',
    guidelines: 'https://www.computer.org/csdl/magazine/sp/write-for-us/14680?title=Author%20Information&periodical=IEEE%20Security%20%26%20Privacy',
  },
};

export function portfolioSubmissionSite(paper: RepositoryPaperProgress | null | undefined, venueId: string, kind: 'portal' | 'guidelines') {
  const candidate = paper?.portfolio?.submission?.candidates.find(item => item.venue_id === venueId);
  const expected = sites[venueId]?.[kind];
  if (!candidate || !expected || (kind === 'portal' ? candidate.portal_url : candidate.guidelines_url) !== expected) {
    throw new EngineError('SUBMISSION_SITE_INVALID', '이 연구의 공식 투고처와 안내 주소를 확인하세요.');
  }
  return expected;
}

/** Submission receipts can change while the reviewed science remains identical. */
export function portfolioScience(paper: RepositoryPaperProgress | null | undefined) {
  if (!paper?.portfolio) return paper;
  const { submission: _submission, ...portfolio } = paper.portfolio;
  return { ...paper, portfolio };
}

type SubmissionWorkflow = { repository_paper?: RepositoryPaperProgress | null;
  author_metadata?: ResearchItem['authorMetadata'];
  artifacts: Record<string, { id: string; size: number; sha256: string }> };

const submissionArtifact = /^repository-portfolio-submission-(?:source|preparation|md|docx|pdf|photo|docx-conversion|pdf-conversion|confirmation|package|manifest|metadata|cover-letter|event|generated-submission-(?:typ|table-layout-lua|pandoc-metadata-json))-[1-9]\d*$/;

function generatedFiles(preparation: PortfolioSubmissionPreparation | null) {
  if (!preparation) return preparation;
  const { current: _current, confirmation: _confirmation, package_artifact_id: _package, package_sha256: _packageHash,
    manifest_artifact_id: _manifest, metadata_artifact_id: _metadata, cover_letter_artifact_id: _letter, ...generated } = preparation;
  return generated;
}

export function verifyPortfolioSubmissionChange(previous: SubmissionWorkflow, updated: SubmissionWorkflow) {
  if (!isDeepStrictEqual(portfolioScience(previous.repository_paper), portfolioScience(updated.repository_paper)) ||
      !isDeepStrictEqual(previous.author_metadata, updated.author_metadata)) {
    throw new EngineError('RESEARCH_STATE_INVALID', '투고 준비가 원고·심사·근거·저자 정보 또는 연구 횟수를 변경했습니다.');
  }
  if (Object.entries(previous.artifacts).some(([id, descriptor]) => !isDeepStrictEqual(updated.artifacts[id], descriptor))) {
    throw new EngineError('RESEARCH_STATE_INVALID', '기존 원고·심사·제출 파일이 누락되거나 바뀌었습니다.');
  }
  for (const [id, descriptor] of Object.entries(updated.artifacts)) {
    if (previous.artifacts[id] ? !isDeepStrictEqual(descriptor, previous.artifacts[id]) :
        !submissionArtifact.test(id)) {
      throw new EngineError('RESEARCH_STATE_INVALID', '투고 준비에서 기존 파일을 바꾸거나 제출 파일 외의 자료를 추가했습니다.');
    }
  }
  const before = previous.repository_paper?.portfolio?.submission;
  const after = updated.repository_paper?.portfolio?.submission;
  if (!after || before?.history.some((record, index) => !isDeepStrictEqual(after.history[index], record))) {
    throw new EngineError('RESEARCH_STATE_INVALID', '기존 접수 기록을 보존하지 않은 투고 상태입니다.');
  }
  if (before?.preparation && before.preparation.sha256 === after.preparation?.sha256 && (
      !isDeepStrictEqual(generatedFiles(before.preparation), generatedFiles(after.preparation)) ||
      before.preparation.confirmation && (!isDeepStrictEqual(before.preparation.confirmation, after.preparation.confirmation) ||
        ['package_artifact_id', 'package_sha256', 'manifest_artifact_id', 'metadata_artifact_id', 'cover_letter_artifact_id'].some(key =>
          before.preparation![key as keyof PortfolioSubmissionPreparation] !== after.preparation![key as keyof PortfolioSubmissionPreparation])))) {
    throw new EngineError('RESEARCH_STATE_INVALID', '동일한 제출 원고 또는 이미 확인한 제출 묶음을 다시 썼습니다.');
  }
}

/** Author changes may invalidate a prepared package, but never rewrite its record. */
export function submissionRecordsPreserved(before: RepositoryPaperProgress | null | undefined, after: RepositoryPaperProgress | null | undefined) {
  const prior = before?.portfolio?.submission, current = after?.portfolio?.submission;
  if (!prior) return !current?.preparation && !current?.history.length;
  if (!current || !isDeepStrictEqual(prior.history, current.history) ||
      !isDeepStrictEqual(prior.portal_record, current.portal_record)) return false;
  const receipt = (value: typeof prior.preparation) => {
    if (!value) return value;
    const { current: _current, ...retained } = value;
    return retained;
  };
  return isDeepStrictEqual(receipt(prior.preparation), receipt(current.preparation));
}
