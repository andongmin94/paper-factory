export interface PortfolioSubmissionPreparationInput {
  expected_draft_sha256: string;
  expected_review_sha256: string;
  expected_author_sha256: string;
  expected_pdf_sha256: string;
  expected_docx_sha256: string;
  author_biography: string;
  keywords: string[];
  photo: { filename: string; media_type: 'image/png' | 'image/jpeg'; base64: string } | null;
  funding_statement: string;
  conflicts_statement: string;
  cover_letter_note: string;
}

export interface PortfolioSubmissionConfirmationInput {
  preparation_sha256: string;
  expected_docx_sha256: string;
  expected_pdf_sha256: string;
  qa: { word_count: number; docx_pages: number; pdf_pages: number; table_count: number; figure_count: number };
  declarations: {
    identity_confirmed: boolean;
    all_authors_approved: boolean;
    originality_confirmed: boolean;
    rights_confirmed: boolean;
    ai_disclosure_reviewed: boolean;
    guidelines_reviewed: boolean;
    all_pages_reviewed: boolean;
  };
}

export interface PortfolioSubmissionRecordInput {
  preparation_sha256: string;
  status: 'submitted' | 'withdrawn' | 'rejected';
  manuscript_id: string;
  occurred_at: string;
  confirmed: boolean;
  note: string;
}

export interface PortfolioSubmissionCandidate {
  venue_id: string;
  name: string;
  portal_url: string;
  guidelines_url: string;
  requirements_checked_at: string;
  limits: { min_words?: number; max_words: number; max_abstract_words: number; max_references: number; visual_word_cost: number };
  expected_binding: Pick<PortfolioSubmissionPreparationInput, 'expected_draft_sha256' | 'expected_review_sha256' |
    'expected_author_sha256' | 'expected_pdf_sha256' | 'expected_docx_sha256'> | null;
  prepare_available: boolean;
  missing: string[];
}

export interface PortfolioSubmissionPreparation {
  artifact_id: string;
  sha256: string;
  at: string;
  venue_id: string;
  current: boolean;
  generation_status: 'completed' | 'failed';
  errors: string[];
  source_artifact_id: string;
  md_artifact_id: string | null;
  docx_artifact_id: string | null;
  pdf_artifact_id: string | null;
  docx_sha256: string | null;
  pdf_sha256: string | null;
  package_artifact_id: string | null;
  package_sha256: string | null;
  manifest_artifact_id: string | null;
  metadata_artifact_id: string | null;
  cover_letter_artifact_id: string | null;
  confirmation: { artifact_id: string; sha256: string; at: string;
    qa: PortfolioSubmissionConfirmationInput['qa']; declarations: PortfolioSubmissionConfirmationInput['declarations'];
    metrics: { biography_words: number; visual_words: number; effective_words: number; abstract_words: number;
      reference_count: number; count_scope: string } } | null;
  author_biography: string;
  keywords: string[];
  funding_statement: string;
  conflicts_statement: string;
  cover_letter_note: string;
  photo: { filename: string; media_type: 'image/png' | 'image/jpeg'; sha256: string; size: number } | null;
  origin: 'explicit_human_submission_preparation';
  externally_verified: false;
}

export interface PortfolioSubmissionRecord {
  artifact_id: string;
  sha256: string;
  at: string;
  status: PortfolioSubmissionRecordInput['status'];
  venue_id: string;
  preparation_sha256: string;
  manuscript_id: string;
  occurred_at: string;
  confirmed: boolean;
  note: string;
  portal_url: string;
  origin: 'explicit_human_submission_record';
  externally_verified: false;
}

export interface PortfolioSubmissionState {
  status: 'not_started' | 'awaiting_file_check' | 'generation_failed' | 'prepared' | 'stale' | 'submitted' | 'withdrawn' | 'rejected';
  selected_venue_id: string | null;
  preparation: PortfolioSubmissionPreparation | null;
  portal_record: PortfolioSubmissionRecord | null;
  history: PortfolioSubmissionRecord[];
  candidates: PortfolioSubmissionCandidate[];
}
