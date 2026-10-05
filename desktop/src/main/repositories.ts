import type { PublicRepository } from '../shared/research.js';

// Account discovery is a bounded public read. Research still freezes the selected repository separately.
export async function listPublicRepositories(accountUrl: string): Promise<PublicRepository[]> {
  const match = /^https:\/\/github\.com\/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))\/?$/.exec(accountUrl);
  if (!match) throw new Error('공개 GitHub 계정 URL 형식을 확인하세요.');
  const owner = match[1];
  const response = await fetch(`https://api.github.com/users/${owner}/repos?type=owner&sort=updated&per_page=100`, {
    headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'Paper-Factory-Standalone' },
    signal: AbortSignal.timeout(30_000), redirect: 'error',
  });
  if (!response.ok) throw new Error('GitHub 공개 저장소 목록을 조회하지 못했습니다. 계정과 조회 한도를 확인하세요.');
  const data: unknown = await response.json();
  if (!Array.isArray(data) || data.length > 100) throw new Error('GitHub 저장소 응답 형식을 확인할 수 없습니다.');
  return data.flatMap(item => {
    if (!item || item.private !== false || typeof item.name !== 'string' ||
      !/^[A-Za-z0-9_.-]+$/.test(item.name) || typeof item.owner?.login !== 'string' ||
      item.owner.login.toLowerCase() !== owner.toLowerCase()) return [];
    return [{ name: item.name, url: `https://github.com/${owner}/${item.name}` }];
  });
}
