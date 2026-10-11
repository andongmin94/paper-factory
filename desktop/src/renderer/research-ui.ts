import type { ResearchSnapshot } from "../shared/research";

export type ResearchAction = (name: string, operation: () => Promise<ResearchSnapshot | boolean | void>) => Promise<void>;

export const repositoryCriterionLabels = { supported_findings: '원문에 근거한 발견', contribution: '연구 기여',
  literature: '관련 연구 비교', method: '분석 방법', presentation: '원고 구성',
  empirical_claims_absent: '주장과 근거 범위', venue_fit: '선택한 학술지 적합성' };

export function attemptCount(value: number | null, maximum?: number) {
  return value === null ? "미확인" : maximum === undefined ? `${value}회` : `${value}/${maximum}회`;
}
