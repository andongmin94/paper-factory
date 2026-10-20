import { isDeepStrictEqual } from 'node:util';
import type { RepositoryPaperProgress, RepositoryPortfolioEvidencePacket } from '../shared/research.js';
import { EngineError } from './engine.js';

export function verifyRepositoryRequestCapacity(prompt: string, model: string, supplementBound = false) {
  // GPT-6.1 Sol: 1,050,000 context, reserve the full 128,000 output and 22,000 framing tokens.
  // UTF-8 bytes conservatively bound text tokens; only an exact native-bound supplement uses this capacity.
  // Official specification: https://developers.openai.com/api/docs/models/gpt-6.1-sol
  const oversized = supplementBound && model === 'gpt-6.1-sol'
    ? Buffer.byteLength(prompt, 'utf8') > 900_000 : prompt.length > 700_000;
  if (oversized) throw new EngineError('REVIEW_CONTEXT_TOO_LARGE', '전체 모델 요청이 해당 모델의 보존 가능한 문맥 한도를 초과했습니다. 전체 근거를 유지하고 요청을 시작하지 않습니다.');
}

export function verifyQualityRequestCapacity(prompt: string, model: string) {
  verifyRepositoryRequestCapacity(prompt, model);
  const bytes = Buffer.byteLength(JSON.stringify({ model, input: [{ role: 'user', content: prompt }], store: false, stream: true }), 'utf8');
  if (bytes > 900_000) throw new EngineError('REVIEW_CONTEXT_TOO_LARGE', '전체 근거를 포함한 실제 모델 요청의 직렬화 크기가 한도를 초과했습니다. 모델에 보내지 않았습니다.');
  return bytes;
}

export function portfolioEvidencePacket(input: unknown, researchId: string): RepositoryPortfolioEvidencePacket {
  const invalid = () => new EngineError('PORTFOLIO_EVIDENCE_INVALID', '보완 자료 패키지는 완전한 원문 파일 1–32개와 출처·해시·기존 심사를 담은 JSON이어야 합니다. 일반 텍스트마다 128 KiB, 정확한 commit·경로·해시에 결속된 완전한 비교 소스마다 256 KiB, 텍스트 합계 512 KiB, 공식 출판사 원 proof에 결속된 PDF는 별도 합계 1 MiB이며 전체 요청은 2 MiB 이내여야 합니다.');
  if (!input || typeof input !== 'object' || Array.isArray(input) || Object.keys(input).sort().join(',') !== 'files,value') throw invalid();
  const packet = input as RepositoryPortfolioEvidencePacket;
  if (!packet.value || typeof packet.value !== 'object' || Array.isArray(packet.value) || !Array.isArray(packet.files) ||
      packet.files.length < 1 || packet.files.length > 32 || packet.files.some(file => !file || typeof file !== 'object' ||
        Object.keys(file).sort().join(',') !== 'contentBase64,name' || typeof file.name !== 'string' || typeof file.contentBase64 !== 'string')) throw invalid();
  try {
    const request = { id: '00000000-0000-0000-0000-000000000000', method: 'workflow.admitPortfolioEvidence',
      params: { researchId, ...packet } };
    if (Buffer.byteLength(JSON.stringify(request) + '\n') > 2 * 1024 * 1024) throw invalid();
  } catch { throw invalid(); }
  return packet;
}

export function verifyPortfolioEvidenceAdmission(prior: RepositoryPaperProgress, next: RepositoryPaperProgress,
  artifacts: Record<string, { sha256: string; size: number }>, packet: RepositoryPortfolioEvidencePacket) {
  const previous = prior.portfolio, portfolio = next.portfolio, supplement = portfolio?.supplementary_evidence;
  const invalid = () => new EngineError('RESEARCH_STATE_INVALID', '보완 자료 등록이 원자료·분석·원고·심사·승인·횟수를 변경했거나 입력 자료와 결속되지 않았습니다.');
  if (!previous || !portfolio || !supplement || supplement.status !== 'admitted' ||
      previous.supplementary_evidence || previous.supplementary_evidence_budget.used !== 0 ||
      portfolio.supplementary_evidence_budget.used !== 1 || portfolio.supplementary_evidence_budget.limit !== 1 ||
      portfolio.supplementary_evidence_available || typeof supplement.sha256 !== 'string' || !supplement.artifact_id || !/^[a-f0-9]{64}$/.test(supplement.sha256) ||
      artifacts[supplement.artifact_id]?.sha256 !== supplement.sha256 ||
      !isDeepStrictEqual(supplement.reviews, packet.value.reviews) ||
      !isDeepStrictEqual(supplement.selection, packet.value.selection) ||
      !isDeepStrictEqual(supplement.comparison, packet.value.comparison) ||
      !isDeepStrictEqual(supplement.affected_venues, supplement.reviews.map(review => review.venue_id))) throw invalid();
  const materials = packet.value.materials;
  const members = packet.value.members as Array<{ name: string; sha256: string; size: number }>;
  if (!Array.isArray(materials) || !Array.isArray(members) || supplement.materials.length !== materials.length ||
      supplement.materials.some((material, index) => {
        const { artifact_id, size, ...original } = material;
        const member = members.find(item => item.name === material.name);
        return !isDeepStrictEqual(original, materials[index]) || !member || size !== member.size ||
          material.sha256 !== member.sha256 || artifacts[artifact_id]?.sha256 !== member.sha256 || artifacts[artifact_id]?.size !== size;
      })) throw invalid();
  if (supplement.all_materials.length !== members.length || supplement.all_materials.some((material, index) => {
    const { artifact_id, ...member } = material;
    return !isDeepStrictEqual(member, members[index]) || artifacts[artifact_id]?.sha256 !== member.sha256 || artifacts[artifact_id]?.size !== member.size;
  })) throw invalid();
  const restored = { ...next, portfolio: { ...portfolio,
    supplementary_evidence: previous.supplementary_evidence,
    supplementary_evidence_budget: previous.supplementary_evidence_budget,
    supplementary_evidence_available: previous.supplementary_evidence_available,
    venues: portfolio.venues.map(venue => {
      const old = previous.venues.find(item => item.venue_id === venue.venue_id);
      if (!old) throw invalid();
      if (supplement.affected_venues.includes(venue.venue_id)) {
        const binding = venue.writer_binding;
        const retained = supplement.reviews.find(review => review.venue_id === venue.venue_id)!;
        if (!binding || binding.supplementary_evidence_sha256 !== supplement.sha256 ||
            binding.phase !== 'venue-manuscript' || binding.venue_id !== venue.venue_id || binding.article_category !== venue.article_category ||
            binding.attempt !== old.draft_attempts + 1 || binding.prior_draft_sha256 !== retained.draft_sha256 ||
            binding.prior_review_sha256 !== retained.review_sha256 || venue.writer_outcome !== null) throw invalid();
        return { ...venue, writer_binding: old.writer_binding, revise_available: old.revise_available, revise_reason: old.revise_reason };
      }
      return venue;
    }) } };
  if (!isDeepStrictEqual(restored, prior)) throw invalid();
}
