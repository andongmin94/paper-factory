export type ResearchPhase = 'idle' | 'plan' | 'redesign' | 'literature' | 'study-review' | 'code' | 'code-review' | 'experiment' | 'manuscript' | 'manuscript-review' | 'export';
export interface SupportingDocument { id: string; name: string; sha256: string; size: number }
export interface ReviewCriterion { passed: boolean; reason: string }
export interface StudyReview {
  accepted: boolean;
  issues: string[];
  question: ReviewCriterion;
  contribution: ReviewCriterion;
  literature: ReviewCriterion;
  comparison: ReviewCriterion;
  sampling: ReviewCriterion;
  feasibility: ReviewCriterion;
  selected_sources: Array<{ source_id: string; excerpt_index: number; relevance: string }>;
}
export interface ManuscriptReview {
  accepted: boolean;
  issues: string[];
  checks: string[];
  contribution: ReviewCriterion;
  literature: ReviewCriterion;
  interpretation: ReviewCriterion;
  presentation: ReviewCriterion;
  remediation?: {
    strategy: 'revise_manuscript' | 'redesign_study' | 'infeasible';
    reason: string;
    actions: Array<{ criterion: 'contribution' | 'literature' | 'interpretation' | 'presentation'; action: string }>;
    evidence_gaps: string[];
  } | null;
}
export interface ResearchItem {
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
  parentResearchId: string | null;
  rootResearchId: string;
  redesignAttempt: number;
  followupResearchId: string | null;
  improvementAvailable: boolean;
}
export interface ResearchSnapshot {
  runtime: { state: 'checking' | 'ready' | 'unavailable'; message: string; versions?: Record<string, string> };
  busy: boolean;
  cleanupResearchIds: string[];
  jobs: ResearchItem[];
  error: { code: string; message: string; action: 'usage' | 'sign-in' | 'retry' | null } | null;
}
export interface CreateResearchInput { source: string; goal: string; model: string; reviewerModel: string }
export interface PublicRepository { name: string; url: string }

export interface ResearchApi {
  researchSnapshot(): Promise<ResearchSnapshot>;
  checkRuntime(): Promise<ResearchSnapshot>;
  createResearch(input: CreateResearchInput): Promise<ResearchSnapshot>;
  resumeResearch(id: string, model: string, reviewerModel: string): Promise<ResearchSnapshot>;
  reviseResearchWriting(id: string, model: string, reviewerModel: string): Promise<ResearchSnapshot>;
  improveResearchWriting(id: string, model: string, reviewerModel: string): Promise<ResearchSnapshot>;
  cancelResearch(id: string): Promise<ResearchSnapshot>;
  addResearchEvidence(id: string): Promise<ResearchSnapshot | false>;
  saveArtifact(id: string, artifactId: string): Promise<boolean>;
  openArtifact(id: string, artifactId: string): Promise<void>;
  showArtifactFolder(id: string, artifactId: string): Promise<void>;
  listPublicRepositories(accountUrl: string): Promise<PublicRepository[]>;
  onResearchSnapshot(listener: (snapshot: ResearchSnapshot) => void): () => void;
}
