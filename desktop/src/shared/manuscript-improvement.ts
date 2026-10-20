export type ImprovementCriterion = 'contribution' | 'evidence' | 'method' | 'comparison' | 'practical_value' |
  'logic' | 'presentation' | 'venue_fit' | 'limitations';
export const improvementCriterionLabels: Record<ImprovementCriterion, string> = {
  contribution: '추가 기여', evidence: '주장과 근거', method: '분석 방법', comparison: '선행·대안 비교',
  practical_value: '실무 적용 가치', logic: '논리', presentation: '표현·구성', venue_fit: '매체 적합성', limitations: '한계의 정확성',
};
export interface ImprovementAssessment {
  venue_id: string; manuscript_sha256: string;
  scores: Array<{ criterion: ImprovementCriterion; score: number; uncertainty: 'low' | 'medium' | 'high';
    passages: string[]; reason: string; required_improvement: string }>;
  essential_errors: string[];
  recommendation: 'consider_submission' | 'revise_before_submission' | 'not_recommended';
  recommendation_reason: string;
  evidence_limits: Array<{ kind: string; criterion: ImprovementCriterion; explanation: string;
    alternatives_attempted: string[]; obtainable_evidence: string }>;
}
export type DevelopmentPurpose = 'develop-plan' | 'develop-evidence' | 'develop-question' | 'develop-design' | 'develop-strengthen' | 'develop-audit' | 'develop-repair' | 'develop-re-audit' | 'develop-write' | 'develop-review';
export type DevelopmentStage = 'plan' | 'evidence' | 'question' | 'design' | 'strengthen' | 'audit' | 'repair' | 're-audit' | 'write' | 'review';
export const developmentPurposeLabels: Record<DevelopmentPurpose, string> = {
  'develop-plan': '연구 질문·비교 설계', 'develop-evidence': '비교·반례 근거 생성', 'develop-audit': '근거 독립 검토',
  'develop-repair': '지적된 근거 보완', 'develop-write': '근거를 반영한 두 원고 집필', 'develop-review': '새 원고 독립 평가',
  'develop-design': '연구 설계·비교 근거 완성', 'develop-re-audit': '보완한 근거 독립 재검토',
  'develop-question': '질문 후보·가까운 방법·필요 근거 설계', 'develop-strengthen': '새 근거로 비교·연구 내용 보완',
};
export const developmentReasonLabels: Record<string, string> = {
  no_answerable_question_from_retained_evidence: '현재 근거로 답할 연구 질문을 확보하지 못했습니다. 후보 비교와 남은 근거를 보존했습니다.',
  checked_research_evidence_required: '검사된 연구 근거가 필요합니다.',
  checked_concrete_work_products_required: '구체적인 연구 산출물의 검사가 필요합니다.',
  independent_method_audit_required: '현재 근거의 독립 방법 검토가 필요합니다.',
  latest_evidence_requires_independent_reaudit: '보완한 현재 근거를 독립 재검토해야 합니다.',
  methodological_repair_required: '독립 검토에서 지적한 근거 보완이 필요합니다.',
  method_audit_not_ready_to_write: '독립 검토에서 집필할 준비가 부족하다고 판단했습니다.',
  current_evidence_independently_ready: '현재 근거와 연구 산출물을 독립 검토해 집필 준비를 확인했습니다.',
  bounded_manuscripts_independently_assessed: '새 원고와 해당 원고의 독립 평가를 보존했습니다.',
  independent_manuscript_assessment_incomplete: '새 원고의 독립 평가가 완료되지 않았습니다.',
  bounded_research_stage_failed: '연구 보완 단계가 완료되지 않아 확보한 산출물을 보존하고 종료했습니다.',
  bounded_research_development_completed: '정해진 연구 보완 작업을 종료했습니다.',
  work_remaining: '정해진 한도에서 연구 보완을 진행합니다.',
};
export type ImprovementPurpose = 'plan' | 'revise' | 'review' | 'focused-select' | 'focused-analyze' | 'focused-write' | 'focused-review' | DevelopmentPurpose;
export interface JournalComplianceReport {
  venue_id: string; checked_at: string;
  items: Array<{ id: string; label: string; status: 'passed' | 'failed' | 'pending';
    stage: 'manuscript' | 'native' | 'submission'; reason: string; source_url: string | null }>;
  metrics: Record<string, unknown> & { effective_words?: number;
    native_word?: { whole_words: number; body_words: number; abstract_words: number;
      reference_count: number; pages?: number; tables?: number; figures?: number } };
  page_qa?: { page_count: number; automatic_checks: boolean } | null;
  blockers: string[]; pending: string[]; prefilter_passed: boolean; content_format_passed: boolean;
  submission_ready: boolean; scientific_merit_assessed: false; author_approval_inferred: false;
}
export interface FocusedFormatPreflight {
  artifact_id: string; sha256: string; content_format_passed: boolean;
  report: { editorial_preparation: Record<string, unknown>; pure: JournalComplianceReport;
    outputs: Record<string, { artifact_id: string; sha256: string }>;
    conversion_receipts: Record<string, unknown>; errors: Array<{ format: string; error: string }>;
    compliance?: JournalComplianceReport; content_format_passed: boolean };
}
export interface FocusedImprovementRound {
  id: string; origin: 'explicit_user_authorized_four_request_extension';
  base_reservations: number; additional_call_limit: 4; closed: boolean; completed_stages: ImprovementPurpose[];
  scope?: string; stop_reason?: string;
  selection?: { sources: Array<{ url: string; comparison_question: string; expected_method_difference: string }>;
    inspect_source_files: string[]; analytical_questions: string[] };
  primary_collection?: { retained_full_bodies: number; retained_characters: number; collection_count: number;
    sources: Array<{ id: string; url: string; title?: string; status: string; failure?: string | null }> };
  analysis_artifact_id?: string; checker_artifact_id?: string;
  analysis_repairs?: Record<string, { artifact_id: string; sha256: string; outcome: 'admitted' | 'rejected' }>;
  writer_repairs?: Record<string, { artifact_id: string; sha256: string; outcome: 'admitted' | 'rejected' }>;
  format_preflight?: Record<string, FocusedFormatPreflight>;
  format_blocked?: Record<string, string>;
}
export interface ResearchWorkProductReport {
  kind: 'native_source_bound_research_work_products';
  internal_consistency_passed: boolean; audit_required: true;
  implementation_validated: false; publication_quality_assessed: false;
  products: Array<{ id: string; kind: 'typed_protocol' | 'source_comparison'; reader_decision: string;
    shared_requirements?: string[]; common_conditions?: string[];
    alternatives?: Array<{ id: string; label: string; implementation_status: 'retained_source' | 'proposed_change';
      implementation_steps: string[]; costs: string[]; applicability_conditions: string[] }>;
    decision_table: Array<{ id: string; condition: string; baseline_decision: string; additional_analysis: string;
      changed_decision: string; limitations: string[] }>;
    matrix?: Array<{ id: string; alternative: string; criterion: string; observation: string;
      implementation_status: 'retained_source' | 'proposed_change' }>;
    dossier?: Array<{ id: string; actor_id: string; phase: string; instruction: string;
      implementation_status: 'retained_source' | 'proposed_change' | 'environment_assumption'; failure_outcome: string }>;
    evidence_limits: string[] }>;
  evidence_limits: string[];
}
export interface ResearchDevelopmentRound {
  id: string; origin: 'explicit_user_authorized_six_request_extension';
  contract_version?: 2 | 3;
  artifact_prefix?: string; relative_root?: string;
  base_reservations: number; additional_call_limit: 6; closed: boolean; completed_stages: DevelopmentStage[];
  repair_required?: boolean; stop_reason?: string;
  strengthening_needed?: boolean;
  selected_question?: { id: string; question: string; reader_decision: string; method_route: 'source_comparison' | 'finite_protocol' } | null;
  agenda_artifact_id?: string; research_design_artifact_id?: string;
  acquisitions?: Array<{ queries?: string[]; sources?: Array<{ id: string; title?: string; status: string; complete_body?: boolean }>; retained_full_bodies?: number }>;
  status?: 'research_in_progress' | 'ready_to_write' | 'bounded_research_report' | 'manuscripts_unassessed' | 'manuscripts_assessed';
  evidence_sha256?: string;
  readiness?: { ready_to_write: boolean; reason: string; evidence_sha256: string | null;
    audit_evidence_sha256: string | null; audit_artifact_id: string | null };
  work_products?: { products: Array<{ id: string; kind: 'typed_protocol' | 'source_comparison'; reader_decision: string }> };
  work_product_report?: ResearchWorkProductReport;
  work_products_artifact_id?: string; work_product_report_artifact_id?: string; work_product_markdown_artifact_id?: string;
  audits?: Array<{ purpose: 'develop-audit' | 'develop-re-audit'; artifact_id: string; sha256: string;
    evidence_sha256: string; ready_to_write: boolean; repair_required: boolean }>;
  evidence_admission_repairs?: Record<string, { artifact_id: string; sha256: string; outcome: 'admitted' | 'rejected' }>;
  audit_admission_repairs?: Record<string, { artifact_id: string; sha256: string; outcome: 'admitted' | 'rejected' }>;
  write_admission_repairs?: Record<string, { artifact_id: string; sha256: string; outcome: 'admitted' | 'rejected' }>;
  review_admission_repairs?: Record<string, { artifact_id: string; sha256: string; outcome: 'admitted' | 'rejected' }>;
  plan_artifact_id?: string; evidence_artifact_id?: string; audit_artifact_id?: string; checker_artifact_id?: string;
  supplement?: { artifact_id: string; sha256: string };
  write_versions?: Record<string, { markdown_artifact_id: string; markdown_sha256: string }>;
  format_preflight?: Record<string, FocusedFormatPreflight>; format_blocked?: Record<string, string>;
  assessment_errors?: Record<string, string>; assessed_venues?: string[];
  plan?: { decision_problem: string; expected_article_value: string; hard_limits: string[];
    cases: Array<{ id: string; reader_decision: string; decisive_condition_flip: string; properties: string[]; evidence_tasks: string[];
      alternatives: Array<{ id: string; label: string; engineering_choice: string; implementation_status: 'actual' | 'proposal' | 'environment_assumption'; policy_assumptions: string[]; costs: string[] }> }> };
  evidence?: { method_scope: 'generated_finite_rules_not_project_execution' | 'source_comparison_not_project_execution'; cross_case_findings: string[]; limitations: string[];
    comparisons: Array<{ source_id: string; established_method: string; local_difference: string; what_is_not_new: string; cost_or_limit: string }>;
    cases: Array<{ id: string; decision_problem: string; policy: string; decision_findings: string[]; limits: string[] }> };
  audit?: { evidence_sha256: string; ready_to_write: boolean; repair_required: boolean; decisive_findings: string[]; honest_limits: string[];
    work_product_findings?: Array<{ product_id: string; verdict: 'faithful' | 'needs_repair' | 'unverifiable'; reason: string; required_repair: string }>;
    correspondence: Array<{ case_id: string; alternative_id: string; target_id: string; verdict: 'faithful' | 'needs_repair' | 'unverifiable'; reason: string; required_repair: string }>;
    repair_actions: Array<{ case_id: string; alternative_id: string; target_id: string; issue: string; exact_change: string; available_evidence_ids: string[]; safely_obtainable: boolean }> };
  checker_summary?: { kind: string; project_execution: false; input_sha256: string; checker_sha256: string; scope: string; issues: string[];
    cases: Array<{ case_id: string; cartesian_state_bound: number; issues: string[];
      alternatives: Array<{ alternative_id: string; reachable_state_count: number; edge_count: number; invariant_checks: number;
        meets_declared_requirements: boolean;
        invariants: Array<{ id: string; status: 'passed' | 'failed' | 'vacuous'; antecedent_states: number }>;
        coverage: Array<{ id: string; required: boolean; status: 'passed' | 'unreachable'; reachable_states: number }> }>;
      negative_controls: Array<{ id: string; alternative_id: string; caught: boolean; original_status: string; mutant_status: string }>;
      alternative_comparisons: Array<{ left: string; right: string; different_properties: string[]; left_meets_requirements: boolean; right_meets_requirements: boolean }>;
      condition_flips: Array<{ id: string; alternative_id: string; property_id: string; decisive: boolean; original_status: string; changed_status: string;
        alternative_outcomes_under_same_condition: Array<{ alternative_id: string; meets_declared_requirements: boolean }> }> }> };
}
export interface ManuscriptImprovement {
  policy: { model_call_limit: number; action_limit: number; same_path_no_progress_limit: 2; target_score: 9 };
  finished: boolean;
  report_artifact_id?: string;
  calls: Array<{ call_id: string; purpose: ImprovementPurpose; venue_id: string | null; outcome: string; error?: string; round_id?: string }>;
  focused_round?: FocusedImprovementRound;
  research_development?: ResearchDevelopmentRound;
  research_development_history?: Array<{ id: string; value: ResearchDevelopmentRound; artifact_id: string; sha256: string;
    quality_report_artifact_id: string | null; quality_report_sha256: string | null }>;
  evidence_collection?: { collection_count?: number; reason: string; sources: Array<{ id: string; url: string; status: string; failure?: string | null }> } | null;
  plan: { selected_direction_id: string; scope_and_limits: string;
    directions: Array<{ id: string; reader_problem: string; added_value: string; closest_baseline: string;
      available_evidence: string; missing_evidence: string; selection_reason: string }> } | null;
  actions: Array<{ id: string; path: string; completed?: boolean; material_progress?: boolean }>;
  reviews: Record<string, ImprovementAssessment[]>;
  review_artifact_ids?: Record<string, Record<string, string>>;
  versions: Record<string, Array<{ markdown_sha256: string; markdown_artifact_id: string }>>;
  next_task: { purpose: ImprovementPurpose; venue_id: string | null; manuscript_sha256: string | null; action_id?: string } | null;
  best_assessments?: Record<string, ImprovementAssessment | null>;
  counts?: { model_attempts: number; actions: number; reviews: number; revisions: number; format_repairs?: number };
  recommendations?: Record<string, { recommendation: ImprovementAssessment['recommendation']; reason: string; target_achieved: boolean }>;
  target_achieved?: boolean;
  stop_reason?: string;
  exports?: Record<string, { outputs: Record<string, { artifact_id: string; sha256: string }>; errors: Array<{ format: string; message: string }>;
    compliance?: JournalComplianceReport }>;
}
