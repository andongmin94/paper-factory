import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { normalizeOrcidInput, type OrcidPublicProfile } from '../shared/orcid';
import type { AuthorMetadataInput } from '../shared/research';
import { Button } from './components/ui/button';

type ImportedField = 'display_name' | 'email' | 'affiliation' | 'biography';

function publicFields(profile: OrcidPublicProfile): Partial<Pick<AuthorMetadataInput, ImportedField>> {
  const organizations = [...new Set(profile.affiliations.map(item => item.organization))];
  return {
    ...(profile.name ? { display_name: profile.name } : {}),
    ...(profile.emails.length === 1 ? { email: profile.emails[0] } : {}),
    ...(organizations.length === 1 ? { affiliation: organizations[0] } : {}),
    ...(profile.biography ? { biography: profile.biography } : {}),
  };
}

export function OrcidAuthorFields({ id, value, setValue, disabled }: {
  id: string; value: AuthorMetadataInput; setValue: Dispatch<SetStateAction<AuthorMetadataInput>>; disabled: boolean;
}) {
  const [profile, setProfile] = useState<OrcidPublicProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const imported = useRef<Partial<Pick<AuthorMetadataInput, ImportedField>>>({});
  const orcid = normalizeOrcidInput(value.orcid ?? '');
  useEffect(() => {
    let cancelled = false;
    setProfile(null); setError(''); setLoading(false);
    if (!orcid || disabled) return;
    const timer = setTimeout(() => {
      setLoading(true);
      void window.paperFactory.lookupPublicOrcidProfile(orcid).then(result => {
        if (cancelled) return;
        setProfile(result);
        const fields = publicFields(result);
        setValue(current => {
          if (normalizeOrcidInput(current.orcid ?? '') !== result.orcid) return current;
          const filled = { ...current };
          for (const key of Object.keys(fields) as ImportedField[]) {
            if (!current[key]?.trim()) { filled[key] = fields[key]!; imported.current[key] = fields[key]; }
          }
          return filled;
        });
      }).catch((failure: unknown) => {
        if (!cancelled) setError(failure instanceof Error ? failure.message : 'ORCID 공개 정보를 조회하지 못했습니다.');
      }).finally(() => { if (!cancelled) setLoading(false); });
    }, 600);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [orcid, retry, disabled, setValue]);

  const organizations = [...new Set(profile?.affiliations.map(item => item.organization) ?? [])];
  const missing = profile && [!profile.name && '이름', !profile.emails.length && '이메일',
    !organizations.length && '현재 소속', !profile.biography && '약력'].filter(Boolean).join('·');
  return <>
    <div className="field"><label htmlFor={`${id}-orcid`}>ORCID 또는 프로필 주소</label>
      <input id={`${id}-orcid`} value={value.orcid ?? ''} disabled={disabled} maxLength={256}
        placeholder="0000-0000-0000-0000 또는 https://orcid.org/..." onChange={event => {
          const input = event.target.value;
          setValue(current => {
            const next = { ...current, orcid: input };
            if (normalizeOrcidInput(input) !== orcid) {
              for (const key of Object.keys(imported.current) as ImportedField[]) {
                if (next[key] === imported.current[key]) next[key] = '';
              }
              imported.current = {};
            }
            return next;
          });
        }} />
      <p className="detail-note">등록된 공개 정보를 빈 항목에 자동으로 채웁니다. 저장한 정보와 직접 입력한 값은 유지하며, 아래에서 확인·수정할 수 있습니다.</p>
      {!!value.orcid?.trim() && !orcid && <p role="alert">올바른 ORCID 번호 또는 공식 프로필 주소를 입력하세요.</p>}
      {loading && <p role="status">ORCID 공개 저자 정보를 조회하고 있습니다.</p>}
      {error && <p role="alert">{error} 다시 조회하거나 아래에 직접 입력하세요.</p>}
      <Button type="button" size="sm" variant="ghost" disabled={disabled || loading || !orcid}
        onClick={() => setRetry(current => current + 1)}>ORCID 공개 정보 다시 조회</Button>
    </div>
    {profile && <section className="space-y-2 rounded-base border-2 border-border p-3" aria-label="ORCID 공개 저자 정보">
      <p className="font-semibold">ORCID 공개 정보 조회 완료</p>
      <p className="detail-note">이름: {profile.name ?? '공개 정보 없음'} · 현재 기관: {organizations.join(', ') || '공개 정보 없음'}</p>
      <p className="detail-note">출처: {profile.sourceUrl} · 조회 시각: {profile.retrievedAt}</p>
      <p className="detail-note">공개 정보 조회이며 ORCID 로그인 인증이나 저자 승인은 아닙니다. 소속의 직위·학력으로 약력을 추정하지 않습니다.</p>
      {missing && <p className="detail-note">ORCID에서 공개하지 않은 정보는 직접 입력하세요: {missing}. 기존 입력값은 유지됩니다.</p>}
      {profile.emails.length > 1 && <div className="field"><label htmlFor={`${id}-orcid-email`}>공개 이메일 중 선택</label>
        <select id={`${id}-orcid-email`} disabled={disabled} value={profile.emails.includes(value.email) ? value.email : ''}
          onChange={event => setValue(current => ({ ...current, email: event.target.value || current.email }))}>
          <option value="">이번 원고의 연락 이메일을 선택하세요</option>
          {profile.emails.map(email => <option key={email} value={email}>{email}</option>)}
        </select></div>}
      {organizations.length > 1 && <div className="field"><label htmlFor={`${id}-orcid-affiliation`}>공개 현재 소속 중 선택</label>
        <select id={`${id}-orcid-affiliation`} disabled={disabled} value={organizations.includes(value.affiliation) ? value.affiliation : ''}
          onChange={event => setValue(current => ({ ...current, affiliation: event.target.value || current.affiliation }))}>
          <option value="">이번 원고에 기재할 소속을 선택하세요</option>
          {organizations.map(organization => <option key={organization} value={organization}>{organization}</option>)}
        </select></div>}
    </section>}
    {([['display_name', '저자 이름'], ['email', '저자 이메일'], ['affiliation', '저자 소속']] as const).map(([key, label]) =>
      <div className="field" key={key}><label htmlFor={`${id}-${key}`}>{label}</label>
        <input id={`${id}-${key}`} type={key === 'email' ? 'email' : 'text'} required value={value[key]} disabled={disabled}
          onChange={event => { const input = event.target.value; delete imported.current[key]; setValue(current => ({ ...current, [key]: input })); }} />
      </div>)}
    <div className="field"><label htmlFor={`${id}-biography`}>저자 약력 (영문, 선택)</label>
      <textarea id={`${id}-biography`} maxLength={4000} value={value.biography ?? ''} disabled={disabled}
        onChange={event => { const input = event.target.value; delete imported.current.biography; setValue(current => ({ ...current, biography: input })); }} />
      <p className="detail-note">저장한 약력은 새 제출 파일의 약력 초안에 채워집니다. 연구비·이해관계·권리·최종 저자 승인은 투고 준비에서 별도로 확인합니다.</p>
      {(value.biography?.length ?? 0) > 4000 && <p role="alert">공개 약력이 4,000자를 초과합니다. 이번 원고에 사용할 약력을 줄여 주세요.</p>}
    </div>
  </>;
}
