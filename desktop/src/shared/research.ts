export type ResearchPhase = 'idle' | 'plan' | 'literature' | 'code' | 'code-review' | 'experiment' | 'manuscript' | 'manuscript-review' | 'export';
export interface SupportingDocument { id: string; name: string; sha256: string; size: number }
export interface ResearchItem {
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
}
export interface ResearchSnapshot {
  runtime: { state: 'checking' | 'ready' | 'unavailable'; message: string; versions?: Record<string, string> };
  busy: boolean;
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
  cancelResearch(id: string): Promise<ResearchSnapshot>;
  addResearchEvidence(id: string): Promise<ResearchSnapshot | false>;
  saveArtifact(id: string, artifactId: string, destinationPath: string): Promise<boolean>;
  openArtifact(id: string, artifactId: string): Promise<void>;
  showArtifactFolder(id: string, artifactId: string): Promise<void>;
  listPublicRepositories(accountUrl: string): Promise<PublicRepository[]>;
  onResearchSnapshot(listener: (snapshot: ResearchSnapshot) => void): () => void;
}
