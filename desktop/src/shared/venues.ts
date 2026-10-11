import catalog from '../../../src/paper_factory/publication_venues.json' with { type: 'json' };

export interface PublicationVenue {
  id: string; name: string; publisher: string; scope: string; article_categories: string[];
  contribution_expectation: string; analysis_expectation: string; evidence_modes: string[];
  guidelines_url: string; scope_url: string;
  verified_limits: { max_words?: number; max_abstract_words?: number; max_references?: number;
    visual_word_cost?: number; insight_count?: number };
  editorial_budget: { target_words: number; abstract_words: number };
  requirements_status: 'checked_scope' | 'checked_numeric_guidance';
}

export interface PublicationTarget {
  venue_id: string; article_category: string; selection_reason: string;
  candidates: Array<{ venue_id: string; fit: 'suitable' | 'needs_evidence' | 'out_of_scope';
    reason: string; missing_evidence: string[] }>;
}
export interface PublicationCatalog {
  schema_version: number; checked_at: string;
  recognition: { status: 'conditional'; scope: string; note: string; sources: string[] };
  venues: PublicationVenue[];
}

export const PUBLICATION_CATALOG = catalog as PublicationCatalog;
export const PUBLICATION_VENUES: readonly PublicationVenue[] = PUBLICATION_CATALOG.venues;
export function getPublicationVenue(id: string | undefined | null, venues: readonly PublicationVenue[] = PUBLICATION_VENUES): PublicationVenue | undefined {
  return venues.find(venue => venue.id === id);
}
