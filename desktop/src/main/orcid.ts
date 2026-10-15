import type { OrcidAffiliation, OrcidPublicProfile } from '../shared/orcid.js';
import { normalizeOrcidInput } from '../shared/orcid.js';

const MAX_RESPONSE_BYTES = 1024 * 1024;
const REQUEST_TIMEOUT_MS = 20_000;
class OrcidLookupError extends Error {}
type RecordValue = Record<string, unknown>;
const object = (value: unknown): RecordValue | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : null;
const publicVisibility = (value: unknown) => typeof value === 'string' && value.toLowerCase() === 'public';
function text(value: unknown, max: number, multiline = false): string | null {
  if (typeof value !== 'string' || value.length > max || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)) return null;
  const result = multiline ? value.trim() : value.replace(/\s+/g, ' ').trim();
  return result || null;
}

// ORCID dates may omit month/day. Keep partial dates rather than inventing precision.
function date(value: unknown): { value: string; first: string; last: string } | null | undefined {
  if (value === null || value === undefined) return null;
  const fields = object(value);
  if (!fields) return undefined;
  const year = object(fields.year)?.value;
  const month = object(fields.month)?.value;
  const day = object(fields.day)?.value;
  if (year == null && month == null && day == null) return null;
  if (typeof year !== 'string' || !/^\d{4}$/.test(year) || Number(year) < 1000 ||
      (month != null && (typeof month !== 'string' || !/^(?:0[1-9]|1[0-2])$/.test(month))) ||
      (day != null && (month == null || typeof day !== 'string' || !/^(?:0[1-9]|[12]\d|3[01])$/.test(day)))) return undefined;
  const first = `${year}-${month ?? '01'}-${day ?? '01'}`;
  const monthDays = new Date(Date.UTC(Number(year), Number(month ?? '12'), 0)).getUTCDate();
  if (day != null && Number(day) > monthDays) return undefined;
  const last = `${year}-${month ?? '12'}-${day ?? String(monthDays).padStart(2, '0')}`;
  return { value: year + (month ? `-${month}` : '') + (day ? `-${day}` : ''), first, last };
}

function affiliations(data: RecordValue, orcid: string, kind: OrcidAffiliation['kind'], today: string): OrcidAffiliation[] {
  const groups = data['affiliation-group'];
  if (!Array.isArray(groups)) throw new OrcidLookupError('ORCID 공개 소속 응답 형식을 확인할 수 없습니다.');
  const result = new Map<string, OrcidAffiliation>();
  for (const group of groups) {
    const summaries = object(group)?.summaries;
    if (!Array.isArray(summaries)) continue;
    for (const entry of summaries) {
      const summary = object(object(entry)?.[`${kind}-summary`]);
      if (!summary || !publicVisibility(summary.visibility)) continue;
      const code = summary['put-code'];
      if (!Number.isSafeInteger(code) || Number(code) < 1 || summary.path !== `/${orcid}/${kind}/${code}`) continue;
      const organization = text(object(summary.organization)?.name, 500);
      const start = date(summary['start-date']);
      const end = date(summary['end-date']);
      if (!organization || start === undefined || end === undefined || (start && start.first > today) || (end && end.last < today)) continue;
      const id = `${kind}-${code}`;
      result.set(id, { id, kind, organization, department: text(summary['department-name'], 500),
        role: text(summary['role-title'], 500), startDate: start?.value ?? null, sourceUrl: `https://orcid.org/${orcid}` });
    }
  }
  return [...result.values()];
}

function profile(orcid: string, responses: RecordValue[], retrievedAt: string): OrcidPublicProfile {
  const [person, employment, education] = responses;
  const name = object(person.name);
  const credit = publicVisibility(name?.visibility) ? text(object(name?.['credit-name'])?.value, 500) : null;
  const names = publicVisibility(name?.visibility)
    ? [text(object(name?.['given-names'])?.value, 250), text(object(name?.['family-name'])?.value, 250)].filter(Boolean).join(' ') : '';
  const emailList = object(person.emails)?.email;
  const emails = Array.isArray(emailList) ? [...new Set(emailList.flatMap(entry => {
    const value = object(entry);
    const email = text(value?.email, 254);
    return publicVisibility(value?.visibility) && value?.verified === true && email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? [email] : [];
  }))] : [];
  const biography = object(person.biography);
  return { orcid, sourceUrl: `https://orcid.org/${orcid}`, retrievedAt, publicOnly: true, authenticated: false,
    name: credit ?? (names || null), emails,
    biography: publicVisibility(biography?.visibility) ? text(biography?.content, 10_000, true) : null,
    affiliations: [...affiliations(employment, orcid, 'employment', retrievedAt.slice(0, 10)),
      ...affiliations(education, orcid, 'education', retrievedAt.slice(0, 10))] };
}

async function publicRecord(orcid: string, section: string, signal: AbortSignal): Promise<RecordValue> {
  const response = await fetch(`https://pub.orcid.org/v3.0/${orcid}/${section}`, {
    headers: { Accept: 'application/json', 'User-Agent': 'Paper-Factory-Standalone' },
    signal, redirect: 'error', credentials: 'omit',
  });
  if (response.status === 404) throw new OrcidLookupError('해당 ORCID 공개 기록을 찾을 수 없습니다. 번호를 확인하세요.');
  if (!response.ok) throw new OrcidLookupError('ORCID 공개 기록을 조회하지 못했습니다. 잠시 후 다시 시도하세요.');
  const length = response.headers.get('content-length');
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_RESPONSE_BYTES)) {
    await response.body?.cancel();
    throw new OrcidLookupError('ORCID 공개 응답이 허용 크기를 초과했습니다.');
  }
  if (!/^(?:application\/json|application\/vnd\.orcid\+json)(?:\s*;|$)/i.test(response.headers.get('content-type') ?? '')) {
    await response.body?.cancel();
    throw new OrcidLookupError('ORCID 공개 응답 형식을 확인할 수 없습니다.');
  }
  const reader = response.body?.getReader();
  if (!reader) throw new OrcidLookupError('ORCID 공개 응답이 비어 있습니다.');
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_RESPONSE_BYTES) {
        await reader.cancel();
        throw new OrcidLookupError('ORCID 공개 응답이 허용 크기를 초과했습니다.');
      }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  let result: RecordValue | null;
  try { result = object(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
  catch { throw new OrcidLookupError('ORCID 공개 응답 형식을 확인할 수 없습니다.'); }
  if (!result || result.path !== `/${orcid}/${section}`) throw new OrcidLookupError('요청한 ORCID와 공개 응답 식별자가 일치하지 않습니다.');
  return result;
}

export async function lookupPublicOrcidProfile(input: string): Promise<OrcidPublicProfile> {
  const orcid = normalizeOrcidInput(input);
  if (!orcid) throw new Error('ORCID 번호 또는 https://orcid.org/번호 형식과 검증 숫자를 확인하세요.');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  timer.unref();
  try {
    const responses = await Promise.all(['person', 'employments', 'educations'].map(section => publicRecord(orcid, section, controller.signal)));
    return profile(orcid, responses, new Date().toISOString());
  } catch (error) {
    if (controller.signal.aborted) throw new Error('ORCID 공개 정보 조회 시간이 만료되었습니다. 다시 시도하세요.');
    // Transport details can contain proxy credentials; show only controlled public-read errors.
    if (error instanceof OrcidLookupError) throw error;
    throw new Error('ORCID 공개 정보에 연결하지 못했습니다. 연결을 확인하고 다시 시도하세요.');
  } finally { clearTimeout(timer); controller.abort(); }
}
