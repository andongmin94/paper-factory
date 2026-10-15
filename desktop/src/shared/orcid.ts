export interface OrcidAffiliation {
  id: string;
  kind: 'employment' | 'education';
  organization: string;
  department: string | null;
  role: string | null;
  startDate: string | null;
  sourceUrl: string;
}

// Anonymous public-record lookup is not ORCID authentication or author approval.
export interface OrcidPublicProfile {
  orcid: string;
  sourceUrl: string;
  retrievedAt: string;
  publicOnly: true;
  authenticated: false;
  name: string | null;
  emails: string[];
  biography: string | null;
  affiliations: OrcidAffiliation[];
}

export function normalizeOrcidInput(input: string): string | null {
  if (typeof input !== 'string' || input.length > 100) return null;
  const match = /^(?:https:\/\/orcid\.org\/)?(\d{4}-\d{4}-\d{4}-\d{3}[\dXx])\/?$/.exec(input.trim());
  if (!match) return null;
  const id = match[1].toUpperCase();
  const digits = id.replaceAll('-', '');
  let total = 0;
  for (const digit of digits.slice(0, 15)) total = (total + Number(digit)) * 2;
  const check = (12 - total % 11) % 11;
  return digits[15] === (check === 10 ? 'X' : String(check)) ? id : null;
}
