import type { RepositoryArticleFormat } from './publication.js';
import type { PublicationCatalog, PublicationTarget } from './venues.js';

export type ResearchPhase = 'idle' | 'submission-plan' | 'source-selection' | 'source-analysis' | 'venue-manuscript' | 'venue-manuscript-repair' | 'venue-manuscript-review' | 'research-questions' | 'question-search-plan' | 'question-literature' | 'question-selection' | 'question-reframing' | 'question-reframing-selection' | 'plan' | 'redesign' | 'redesign-plan' | 'redesign-review' | 'literature-plan' | 'literature' | 'study-review' | 'code' | 'code-review' | 'experiment' | 'evidence-selection' | 'manuscript-claim' | 'manuscript' | 'manuscript-repair' | 'manuscript-review' | 'export';

export interface SupportingDocument { id: string; name: string; sha256: string; size: number }
export interface ReviewCriterion { passed: boolean; reason: string }
export interface LiteratureSelection { source_id: string; excerpt_index: number; relevance: string }
export interface SubmissionContract {
  article_type: 'empirical' | 'finite_enumeration' | 'formal';
  language: string; target_audience: string; core_claim: string;
  claim_obligations: Array<{ id: string; claim: string; validation_mode: SubmissionContract['article_type']; required_evidence: string; importance: string }>;
  venue_candidates: Array<{ name: string; rationale: string; official_requirements_status: 'pending'; official_requirements: never[] }>;
  selected_venue: null;
}
export interface ManuscriptClaim {
  mode: SubmissionContract['article_type']; claim: string; scope: string;
  outcome: 'positive' | 'negative' | 'null' | 'mixed'; scope_justification: string;
  analysis_keys: string[]; fixture_labels: string[]; proof_section: string | null; proof_quote: string | null;
}
export interface SubmissionReadiness {
  ready: boolean; status: 'contract_pending' | 'manuscript_pending' | 'venue_pending' | 'visual_pending' | 'ready'; blockers: string[];
  science_verified?: boolean; venue_verified?: boolean; formats_verified?: boolean; visual_verified?: boolean; author_verified?: boolean;
  contract_sha256?: string; manuscript_sha256?: string; pdf_sha256?: string; package_sha256?: string; canonical_sha256?: string; author_sha256?: string;
  visual_pages?: Array<{ number: number; image_sha256: string; text_sha256: string; image_artifact_id: string }>;
  author_metadata?: { metadata_complete: boolean; explicit_metadata?: boolean; verified: boolean; missing: string[] };
}
export interface AuthorMetadataInput {
  display_name: string; email: string; affiliation: string;
  given_name?: string; family_name?: string; orcid?: string; department?: string;
  city?: string; country?: string; scholar_id?: string; github?: string; homepage?: string;
}
export interface SubmissionRequirements {
  origin: string; bindings: Record<string, unknown>; venue: string; url: string;
  status: 'retained' | 'failed'; http_status: number | null; content_type: string | null;
  raw_sha256: string; raw_artifact_id: string; text_artifact_id: string | null; text_sha256: string | null;
  error: string | null; scope: string;
}
export interface ResearchLedger {
  entries: Array<Record<string, unknown>>;
}
export interface StudyRedesignReview {
  accepted: boolean;
  issues: string[];
  scientific_difference: ReviewCriterion;
  prior_evidence: ReviewCriterion;
  feasibility: ReviewCriterion;
}
export interface PreparationRepair {
  original_candidate_sha256: string;
  prior_review_sha256: string;
  changes: Array<{ issue_index: number; required_change: string; actual_change: string;
    changed_fields: Array<'procedure' | 'analysis_method'> }>;
}
export interface PreparationRepairReceipt {
  origin: 'native_host_submission'; scope: string;
  original_candidate_sha256: string; prior_review_sha256: string; candidate_sha256: string;
  parent_basis: unknown; parent_repair_sha256: string | null;
  actual_changed_fields: Array<'procedure' | 'analysis_method'>; value: PreparationRepair;
}
export interface PreparationOriginal {
  candidate: Record<string, unknown>; review: StudyRedesignReview; repair: unknown;
  artifact_ids: { candidate: string; review: string; repair: string | null };
}
export interface PublicationReadiness {
  novelty: ReviewCriterion;
  significance: ReviewCriterion;
  validation: ReviewCriterion;
  claim: string;
  scope: string;
  evidence_mode: 'formal' | 'empirical' | 'finite_enumeration';
  evidence_basis: string;
  closest_work: Array<{ source_id: string; excerpt_index: number; quote: string; known_result: string; difference: string }>;
  analysis_keys: string[];
  fixture_labels: string[];
  proof_section: string | null;
  proof_quote: string | null;
}
export interface StudyReview {
  accepted: boolean;
  issues: string[];
  question: ReviewCriterion;
  contribution: ReviewCriterion;
  literature: ReviewCriterion;
  comparison: ReviewCriterion;
  sampling: ReviewCriterion;
  feasibility: ReviewCriterion;
  selected_sources: LiteratureSelection[];
  publication_readiness?: PublicationReadiness | null;
}
export interface ManuscriptReview {
  accepted: boolean;
  issues: string[];
  checks: string[];
  contribution: ReviewCriterion;
  literature: ReviewCriterion;
  interpretation: ReviewCriterion;
  presentation: ReviewCriterion;
  observed_claim?: ManuscriptClaim;
  claim_scope?: ReviewCriterion;
  publication_readiness?: PublicationReadiness | null;
  remediation?: {
    strategy: 'revise_manuscript' | 'redesign_study' | 'infeasible';
    reason: string;
    actions: Array<{ criterion: 'contribution' | 'literature' | 'interpretation' | 'presentation'; action: string }>;
    evidence_gaps: string[];
  } | null;
}
export interface RepositorySourceEvidence {
  id: string; path: string; sha256: string; quote: string; interpretation: string;
}
export interface RepositoryPaperPlan {
  publication_target: PublicationTarget;
  article_type: 'software_tool' | 'design_case_study' | 'technical_analysis';
  title: string; question: string; contribution: string; analysis_method: string;
  comparison_dimensions: string[]; source_files: string[]; source_evidence: RepositorySourceEvidence[];
  literature_queries: string[]; limitations: string[];
}
export interface RepositoryPaperDraft {
  title: string; sections: Array<{ heading: string; text: string }>;
  source_evidence: RepositorySourceEvidence[];
  literature_evidence: Array<{ source_id: string; text_sha256: string; quote: string; interpretation: string }>;
  document_evidence: Array<{ source_id: string; text_sha256: string; quote: string; interpretation: string }>;
  revision: { prior_draft_sha256: string; changes: string[] } | null;
}
export interface RepositoryAnalysis {
  method: string;
  codebook: Array<{ dimension: string; definition: string }>;
  units: Array<{ id: string; label: string; evidence_ids: string[];
    observations: Array<{ dimension: string; finding: string; evidence_ids: string[] }> }>;
  findings: Array<{ id: string; claim: string; unit_ids: string[]; evidence_ids: string[]; limitations: string }>;
  counterexamples: Array<{ finding_id: string; condition: string; evidence_ids: string[]; implication: string }>;
  source_evidence: RepositorySourceEvidence[];
  literature_evidence: RepositoryPaperDraft['literature_evidence'];
  document_evidence: RepositoryPaperDraft['document_evidence'];
  limitations: string[];
}
export interface RepositoryAction {
  action: 'revise_source_analysis' | 'retrieve_literature' | 'retrieve_documentation' | 'revise_manuscript' | 'human_validation' | 'infeasible';
  target: string; required_change: string; verification: string;
}
export interface RepositoryRevisionOutline {
  heading: string; instruction: string;
}
export interface RepositoryAnalysisProvenance {
  method: string; execution_performed: false; human_analysis_verified: false; human_approval_verified: false;
  model_calls: Array<{ artifact_id: string; sha256: string; phase: 'source-selection' | 'plan' | 'source-analysis' | 'manuscript'; model: string }>;
}
export interface RepositoryRevisionFeedback {
  feedback: string; draft_sha256: string; markdown_sha256: string; review_sha256: string | null;
  bindings: Record<string, unknown>; issues: string[]; next_actions: RepositoryAction[];
  revision_outline: RepositoryRevisionOutline[];
}
export interface RepositoryContentAssessment {
  comparison: ReviewCriterion; contribution: ReviewCriterion;
  /** Blocking content defects only; optional advice belongs in criterion reasons. */
  issues: string[];
  /** Empty when both content criteria pass. */
  next_actions: RepositoryAction[];
  literature_queries: string[];
  pdf_candidates: Array<{ doi: string; title: string; url: string }>;
  revision_outline: RepositoryRevisionOutline[];
}
export interface RepositoryPaperReview {
  criteria: Record<'supported_findings' | 'contribution' | 'literature' | 'method' | 'presentation' | 'empirical_claims_absent' | 'venue_fit', ReviewCriterion>;
  /** Blocking manuscript defects only; positive findings and optional advice belong in criterion reasons. */
  issues: string[]; next_actions: RepositoryAction[];
  content_assessment?: RepositoryContentAssessment | null;
}
export interface RepositoryReferenceSelection {
  references: Array<{ url: string; purpose: 'comparison' | 'venue'; reason: string }>;
  venue_suggestions: Array<{ name: string; url: string; reason: string }>;
}
export interface RepositoryPortfolioFrame {
  research_id: string; portfolio_start_sha256: string; source_digest: string; source_commit: string;
  plan_sha256: string; base_analysis_sha256: string | null; catalog_sha256: string; guidance_sha256: string;
  literature_sha256: string | null;
  portfolio_analysis_sha256: string | null;
  analysis_revision_sha256?: string;
  prior_review_sha256?: string;
  supplementary_evidence_sha256?: string;
  phase: 'source-analysis' | 'venue-manuscript' | 'venue-manuscript-repair' | 'venue-manuscript-review';
  venue_id: string | null; article_category: string | null; attempt: number;
  prior_draft_sha256: string | null; draft_sha256: string | null; markdown_sha256: string | null;
  repair?: { original_inference_artifact_id: string; original_inference_sha256: string;
    original_prompt_sha256: string; partial_text_sha256: string; original_attempt: number };
}
export interface RepositoryPortfolioOutputCorrection {
  artifact_id: string; sha256: string; status: 'completed' | 'failed' | 'interrupted';
  original_draft_sha256: string; original_markdown_sha256: string; original_review_sha256: string;
  input_artifact_id: string; input_sha256: string;
  errors: Array<{ format: 'pdf' | 'docx'; message: string }>;
  outputs?: Partial<Record<'pdf' | 'docx', { artifact_id: string; sha256: string }>>;
}
export interface RepositoryPortfolioLayoutExport extends RepositoryPortfolioOutputCorrection {
  scope: 'canonical-source-labels-and-docx-captions';
  original_artifact_id: string; original_sha256: string;
  original_input_artifact_id: string; original_input_sha256: string;
  model_calls: 0; scientific_approval_changed: false;
  layout_proof: { original_markdown_sha256: string; formatted_markdown_sha256: string;
    scientific_body_sha256_before: string; scientific_body_sha256_after: string };
}
export interface RepositoryPortfolioVenue {
  venue_id: string; article_category: string;
  draft_attempts: number; review_attempts: number; admitted_drafts: number;
  draft: RepositoryPaperDraft | null; review: RepositoryPaperReview | null; draft_sha256: string | null;
  artifact_ids: { draft: string | null; markdown: string | null; review: string | null; pdf: string | null; docx: string | null };
  status: 'pending_analysis' | 'pending_draft' | 'writing_interrupted' | 'pending_review' | 'review_interrupted' | 'content_ready' | 'needs_revision';
  writer_binding: RepositoryPortfolioFrame | null; reviewer_binding: RepositoryPortfolioFrame | null;
  writer_outcome: RepositoryPortfolioOutcome; reviewer_outcome: RepositoryPortfolioOutcome;
  repair_attempts: number; repair_binding: RepositoryPortfolioFrame | null; repair_outcome: RepositoryPortfolioOutcome;
  export_status: 'not_started' | 'completed' | 'failed' | 'interrupted';
  export: { artifact_id: string; sha256: string; errors: Array<{ format: 'pdf' | 'docx'; message: string }>;
    original_artifact_id?: string; original_sha256?: string } | null;
  export_repair_available: boolean; export_repair_attempts: number; export_repair_total: number;
  format_export_available: boolean; format_export_attempts: number;
  format_export: RepositoryPortfolioOutputCorrection | null;
  layout_export_available: boolean; layout_export_attempts: number;
  layout_export: RepositoryPortfolioLayoutExport | null;
  revise_available: boolean; revise_reason: string;
  analysis_current: boolean; scientific_ready: boolean; content_ready: boolean; submission_ready: false;
}
export type RepositoryPortfolioOutcome = 'started' | 'completed' | 'failed' | 'interrupted' | null;
export interface RepositoryPortfolioEvidencePacket {
  value: Record<string, unknown>;
  files: Array<{ name: string; contentBase64: string }>;
}
export interface RepositoryPortfolioSupplement {
  artifact_id: string | null; sha256: string | null; status: 'admitted' | 'failed' | 'interrupted';
  affected_venues: string[];
  all_materials: Array<{ name: string; original_path?: string; artifact_id: string; sha256: string; size: number }>;
  reviews: Array<{ venue_id: string; draft_artifact_id: string; draft_sha256: string;
    review_artifact_id: string; review_sha256: string }>;
  materials: Array<{ id: string; artifact_id: string; name: string; sha256: string; size: number;
    kind: 'case_source' | 'requirement' | 'primary_body' | 'supplied_result'; title: string; url: string;
    provenance: 'supplied_snapshot' | 'supplied_primary_copy' | 'supplied_interpretation';
    case_id?: string; path?: string; commit?: string;
    primary_source?: Record<string, unknown>; primary_proof?: Record<string, unknown> }>;
  selection: { rationale: string; lineage: string } | null;
  comparison: { protocol: string; provenance: 'supplied_interpretation';
    witnesses: Array<{ id: string; material_id: string; quote: string }>;
    results: Array<{ claim: string; evidence_ids: string[]; limitations: string }> } | null;
}
export interface RepositoryPortfolioProgress {
  artifact_id: string; sha256: string; bindings: Record<string, unknown>;
  targets: Array<{ venue_id: string; article_category: string }>;
  analysis: RepositoryAnalysis | null; analysis_sha256: string | null; analysis_binding: RepositoryPortfolioFrame | null;
  analysis_outcome: RepositoryPortfolioOutcome;
  analysis_revision_required: boolean; analysis_revision_available: boolean;
  analysis_revision: { artifact_id: string; sha256: string; prior_analysis_sha256: string;
    actions: RepositoryAction[]; affected_venues: string[]; status: 'planned' | 'completed' | 'incomplete' } | null;
  literature: unknown; literature_sha256: string | null;
  literature_followup_available: boolean;
  documentation_followup_available: boolean;
  literature_budget: { used: number; limit: 3 };
  pdf_budget: { base_used: number; additional_limit: number; additional_used: number; total_used: number;
    base_reservations_sha256: string };
  literature_collections: Array<{ artifact_id: string; sha256: string; attempt: number;
    queries: string[]; status: 'completed' | 'interrupted' }>;
  supplementary_evidence: RepositoryPortfolioSupplement | null;
  supplementary_evidence_budget: { used: number; limit: 1 };
  supplementary_evidence_available: boolean;
  guidance: { artifact_id: string; sha256: string; scope: string; sources: Array<{
    venue_id: string; url: string; status: 'retained' | 'failed'; failure: string | null;
    text_artifact_id: string | null; text_sha256: string | null; text_size: number; text_chars: number;
  }> } | null;
  venues: RepositoryPortfolioVenue[]; all_content_ready: boolean; completed: number; total: number;
}
export interface RepositoryPaperProgress {
  portfolio?: RepositoryPortfolioProgress | null;
  publication_venues?: PublicationCatalog | null;
  analysis?: RepositoryAnalysis | null;
  analysis_attempts: number;
  analysis_revision_required: boolean;
  plan: RepositoryPaperPlan | null; literature: unknown; draft: RepositoryPaperDraft | null;
  review: RepositoryPaperReview | null; revision_available: boolean;
  scientific_ready: boolean; submission_ready: false;
  venueFormat?: RepositoryArticleFormat | null;
  content_assessment?: RepositoryContentAssessment | null; content_assessment_sha256?: string | null;
  content_ready?: boolean | null; assessment_available?: boolean;
  draft_sha256?: string | null;
  analysis_provenance: RepositoryAnalysisProvenance;
  revision_feedback: RepositoryRevisionFeedback | null; revision_feedback_sha256: string | null;
  prior_feedback: { draft: RepositoryPaperDraft; bindings: Record<string, unknown>; draft_sha256: string;
    markdown_sha256: string; review_sha256: string | null; review: RepositoryPaperReview | null;
    content_assessment: RepositoryContentAssessment | null; revision_feedback: RepositoryRevisionFeedback;
    revision_feedback_sha256: string; next_actions: RepositoryAction[] } | null;
  readiness?: { scientific_ready: boolean; submission_ready: false; reason: string };
  artifact_ids: Record<string, string>; bindings: Record<string, unknown>;
  manuscript_bindings?: Record<string, unknown>;
  conversion_errors?: Array<{ format: string; message: string }>;
  next_actions: RepositoryPaperReview['next_actions'];
  references?: Array<{ id: string; url: string; purpose: 'comparison' | 'venue'; status: 'retained' | 'failed';
    text_sha256: string | null; text_artifact_id: string | null; fetched_at: string; reason: string; failure: string | null }>;
  reference_collections?: Array<{ artifact_id: string; attempt: number; status: 'reserved' | 'completed';
    selection: RepositoryReferenceSelection; at: string }>;
  venue_suggestions?: Array<{ name: string; url: string; reason: string; status: 'pending' }>;
  formatting_receipts?: Array<{ artifact_id: string; draft_attempt: number; attempt: number; status: 'reserved' | 'completed';
    markdown_sha256: string; draft_sha256: string; review_sha256: string | null;
    input_artifact_id?: string; input_sha256?: string; author_artifact_id?: string | null; author_sha256?: string | null;
    outputs: Record<string, { artifact_id: string; sha256: string; conversion_artifact_id: string }>;
    errors: Array<{ format: string; message: string }> }>;
}
export interface ResearchItem {
  portfolioUnsentRequestAvailable?: boolean;
  researchMode?: 'empirical' | 'repository_analysis';
  repositoryPaper?: RepositoryPaperProgress | null;
  resumeKind: 'preparation' | 'authoring' | null;
  id: string;
  source: string;
  goal: string;
  model: string;
  reviewerModel: string;
  phase: ResearchPhase;
  pipeline: 'idle' | 'running' | 'paused' | 'failed' | 'completed';
  stage: string;
  status: string;
  code: string | null;
  message: string | null;
  updatedAt: string;
  artifacts: Array<{ id: string; sha256: string; size: number }>;
  supportingDocuments: SupportingDocument[];
  studyReview: StudyReview | null;
  manuscriptReview: ManuscriptReview | null;
  preparationRedesignReview: StudyRedesignReview | null;
  preparationRepairAttempt: number | null;
  preparationRepair: PreparationRepairReceipt | null;
  preparationOriginal: PreparationOriginal | null;
  parentResearchId: string | null;
  rootResearchId: string;
  proposalAttempt: number | null;
  studyLiteratureAttempt: number | null;
  redesignQuestionEvidenceCollections: number | null;
  redesignQuestionSearchRepairPlans: number | null;
  redesignQuestionSearchRepairCollections: number | null;
  redesignQuestionReframingPlans: number | null;
  redesignQuestionReframingComparisons: number | null;
  redesignQuestionReframingStatus?: 'planning' | 'proposed' | 'reviewing' | 'ready' | 'held' | 'incomplete' | null;
  questionLiteratureFollowupPlans?: number | null;
  questionLiteratureFollowupCollections?: number | null;
  questionLiteratureFollowupStatus?: 'planning' | 'planned' | 'ready' | 'held' | 'incomplete' | null;
  codeAttempt: number | null;
  executionAttempt: number | null;
  draftAttempt: number | null;
  manuscriptAvailable: boolean | null;
  submissionContract: { value: SubmissionContract; bindings: Record<string, unknown>; scope: string } | null;
  submissionReadiness: SubmissionReadiness | null;
  manuscriptClaim: { value: ManuscriptClaim; bindings: Record<string, unknown>; scope: string } | null;
  researchLedger: ResearchLedger | null;
  plannedClaim: { claim: string; scope: string; mode: ManuscriptClaim['mode'] } | null;
  submissionRequirements: SubmissionRequirements | null;
  submissionConfirmation: Record<string, unknown> | null;
  authorMetadata: { origin: string; value: AuthorMetadataInput; bindings: Record<string, unknown>; scope: string;
    artifact_id?: string; sha256?: string; selection_artifact_id?: string } | null;
  redesignAttempt: number | null;
  followupResearchId: string | null;
  improvementAvailable: boolean;
}
export interface ResearchSnapshot {
  runtime: { state: 'checking' | 'ready' | 'unavailable'; message: string; versions?: Record<string, string>; repositoryAnalysisReady?: boolean };
  busy: boolean;
  cleanupResearchIds: string[];
  jobs: ResearchItem[];
  error: { code: string; message: string; action: 'usage' | 'sign-in' | 'retry' | null } | null;
}
export interface CreateResearchInput { source: string; goal: string; model: string; reviewerModel: string;
  researchMode?: 'repository_analysis' }
export interface PublicRepository { name: string; url: string }

export interface ResearchApi {
  researchSnapshot(): Promise<ResearchSnapshot>;
  checkRuntime(): Promise<ResearchSnapshot>;
  createResearch(input: CreateResearchInput): Promise<ResearchSnapshot>;
  resumeResearch(id: string, model: string, reviewerModel: string): Promise<ResearchSnapshot>;
  improveResearch(id: string, model: string, reviewerModel: string): Promise<ResearchSnapshot>;
  requestRepositoryRevision(researchId: string, feedback: string): Promise<ResearchSnapshot>;
  requestRepositoryPortfolio(researchId: string): Promise<ResearchSnapshot>;
  reformatRepositoryPortfolioDraft(researchId: string, venueId: string): Promise<ResearchSnapshot>;
  correctRepositoryPortfolioLayout(researchId: string, venueId: string): Promise<ResearchSnapshot>;
  admitRepositoryPortfolioEvidence(researchId: string, packet: RepositoryPortfolioEvidencePacket): Promise<ResearchSnapshot>;
  reformatResearchDraft(id: string): Promise<ResearchSnapshot>;
  setResearchAuthorMetadata(id: string, value: AuthorMetadataInput): Promise<ResearchSnapshot>;
  cancelResearch(id: string): Promise<ResearchSnapshot>;
  addResearchEvidence(id: string): Promise<ResearchSnapshot | false>;
  saveArtifact(id: string, artifactId: string): Promise<boolean>;
  openArtifact(id: string, artifactId: string): Promise<void>;
  showArtifactFolder(id: string, artifactId: string): Promise<void>;
  listPublicRepositories(accountUrl: string): Promise<PublicRepository[]>;
  onResearchSnapshot(listener: (snapshot: ResearchSnapshot) => void): () => void;
}
