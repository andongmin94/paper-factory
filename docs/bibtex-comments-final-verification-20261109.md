# BibTeX 필드 주석 수정 및 최종 인계

2026-11-09 UTC. 마지막 추가 지시 5/5의 로컬 구현·검증 기록이다. 기준은 `0d645765643a05bfed23915cbc2791e0b42de8f2`이며, 작업 브랜치는 `fix/bibtex-entry-comments`다. 이전 커밋을 재작성하지 않았다. 최종 커밋 SHA와 산출물 해시는 이번 `round6/handoff.json`에 기록한다.

## 원격과 로컬 범위

시작과 검증 종료 시 GitHub의 기본 브랜치 및 열린 PR을 읽었다. 마지막 확인은 2026-11-09 10:33 UTC다.

| 대상 | 확인한 상태 |
| --- | --- |
| 실제 원격 main | `1a0b33ac0a350850d011a44d725a66a2c78ac42e` |
| 열린 PR | Draft #2 한 개, head `659fa818fab67fae2259d758c4472e423fa157ed` |
| PR 병합 상태 | `merged=false`, `mergeable=false`, `mergeable_state=dirty` |
| 이번 시작점 | main 위의 미게시 `5b44535` → `0d64576` |
| 이번 반영 | 위 두 JOSS 커밋 뒤에 BibTeX 주석 수정 로컬 커밋 추가 |

PR API의 base snapshot은 이전 `1aff3b7`였으므로 최신 main SHA는 별도 branch API로 확인했다. 이번 패치의 기본 브랜치 기준은 실제 원격 `1a0b33a`다. 로컬에 남은 예전 `main` ref와 혼동하지 않는다.

현재 main과 PR #2를 `git merge-tree --write-tree`로 진단한 결과는 **충돌 exit 1**이다. 충돌 파일은 README.md, references/tools.md, scripts/editorial_checks.py, scripts/export_manuscript.py, tests/test_repository_snapshot.py, tests/test_skill_export.py의 6개다. 실제 merge/cherry-pick, 충돌 해결, PR head 변경은 하지 않았다. 이 명령이 만드는 참조되지 않은 tree/blob 객체 외에 기존 refs와 worktree 상태는 유지됐다.

원격 게시, Draft PR 생성, 병합, 배포, 릴리스, 권한·보안 설정 변경은 이번 작업에 포함하지 않았다. `5b44535`부터의 세 수정은 모두 미게시 상태다.

## 공식 계약과 구현 결정

- [JOSS의 공식 인용 안내](https://joss.readthedocs.io/en/latest/paper.html#citations)는 `paper.bib`에 BibLaTeX 서지 데이터를 두며 plain BibTeX도 허용한다.
- [Pandoc 공식 안내](https://pandoc.org/MANUAL.html#specifying-bibliographic-data)는 `.bib`를 BibLaTeX, `.bibtex`를 BibTeX로 해석하며 title 등의 필드에는 LaTeX 해석을 추가로 적용한다고 설명한다.
- [Pandoc 3.9의 실제 reader](https://github.com/jgm/pandoc/blob/3.9/src/Text/Pandoc/Citeproc/BibTeX.hs#L806-L907)는 구조 위치의 `spaces'`에서 `%` 줄 주석을 건너뛴다. `inBraces`와 `inQuotes`는 `%`를 리터럴 원문으로 읽는다.
- [고전 BibTeX의 공식 구현](https://github.com/TeX-Live/texlive-source/blob/a9a9dca114301dac0eb0063f1e5ab0f27e90a3f0/texk/web2c/bibtex.web)은 entry 내부 공백 처리에 같은 `%` 처리를 두지 않는다. 이번 동작을 모든 BibTeX 구현의 공통 문법이라고 보장하지 않는다.

**결정:** 기존 importer와 JOSS 소스 검사가 Pandoc에서 허용되는 **필드·값의 구조 경계에 있는 `%` 줄 주석**을 수용한다. braced/quoted 값 안의 `%`, escaped `\%`, URL percent escape, 중첩 괄호, 기존 macro·문자열 연결의 원문은 유지한다. entry key 문법이나 다른 BibLaTeX 기능의 범위는 확장하지 않았다.

실제 Pandoc 3.9의 두 reader를 14개 입력에 실행한 28회 결과를 보존했다. 정상 12개 입력은 각각 exit 0과 빈 stderr, 잘못된 구문 2개는 각각 exit 64였다. 주석 속 가짜 `@entry`, 괄호·따옴표·쉼표·`#`는 구문이 되지 않았다. CRLF, 중첩 값, `@string`과 `#`도 확인했다.

원문 보존과 렌더링 의미는 다르다. 예를 들어 title의 이스케이프 없는 `%`는 reader가 수용한 뒤 LaTeX 해석에서 그 줄의 뒤쪽 텍스트를 숨길 수 있다. escaped `\%`와 URL의 `%20`·`%25`도 별도로 확인했다. CSL JSON 변환 성공을 Inara/PDF의 성공이나 화면상 동일성으로 표시하지 않는다.

## 수정 전 재현

다음과 같은 필드 주석이 기존 파서에서 `Invalid BibTeX ... Expected end of text`로 거부됐다.

```bibtex
title = {A Retained {Research} Tool}, % supplied annotation
```

이 문제는 이전 회차에서 main, `5b44535`, `0d64576`, 그리고 PR #2에서 추출한 기존 함수에서도 재현했다. 이번에는 production을 변경하기 전에 실제 `0d64576` 함수에 신규 회귀 40개를 실행했다.

```text
27 failed, 13 passed, 133 deselected in 4.41s
```

13개 통과는 기존 리터럴 보존 6개와 잘못된 입력 거부 7개다. 실패 27개는 새로 지원해야 하는 정상 주석의 거부였다. 두 JOSS 통합 사례는 먼저 실제 Pandoc의 bibtex/biblatex reader가 정상 입력임을 확인한 뒤 importer에서 실패했다. 테스트 파일의 SHA-256을 수정 전후 비교해, 같은 테스트를 완화하지 않고 실행했음을 확인했다.

독립 설치 ZIP의 수정 전 CLI에서도 주석 없는 입력은 import·preflight·export가 모두 exit 0이었다. 정상 주석을 추가한 입력은 세 경로 모두 exit 2로 거부됐다. 잘못된 구문은 별도 세 경로에서 정상적으로 거부됐다. 이 **9개 실행**은 수정 전 결함과 정상 거부를 구분해 기록했다.

## 최소 변경

실행 코드 수정은 [scripts/import_references.py](../scripts/import_references.py) 하나다. 9줄 추가·4줄 삭제로 기존 pyparsing 표현식에 다음을 반영했다.

1. 줄 끝까지 읽는 주석 표현식을 재사용한다.
2. 필드 시작과 이름/등호 사이, 값 앞뒤, 쉼표와 `#` 주변에서만 주석을 소비한다.
3. 기존 `braced`, `quoted`, `escaped`, `original_text_for`, `Located`, `parse_with_tabs`, macro 확장과 source.raw 슬라이싱은 유지한다.

입력 전체를 치환하거나 `%` 뒤를 지우는 전처리는 없다. 파서·의존성·호환 계층·새 프레임워크를 추가하지 않았다. PR #2의 다른 기능도 가져오지 않았다.

pyparsing의 `.ignore()`는 복합 표현식의 자식으로 재귀 전달되므로 전역 설정 대신 문법 경계를 명시했다. 다만 독립 최소 프로브에서 현재 래퍼와 전역 ignore의 조합으로 원문 손상이 재현된 것은 아니다. 이를 이미 확인된 데이터 손실이라고 주장하지 않는다.

추가 변경 파일은 다음과 같다.

| 파일 | 목적 |
| --- | --- |
| tests/test_import_references.py | 신규 38개 경계 회귀. 기존 unittest 메서드 30개는 변경 없음 |
| tests/test_joss_export.py | 실제 두 Pandoc reader 비교 및 LF/BOM+CRLF JOSS 패키지 통합 2개 |
| references/tools.md | 지원하는 주석 범위, raw/바이트 보존과 후속 LaTeX 해석 구분 |
| 이 문서 | 이번 회차와 전체 이력의 최종 인계 |

기존 `_publication_joss.py`, Word 출력, 근거·Git 환경 구현은 이번 커밋에서 수정하지 않았다.

## 회귀 범위와 결과

신규 importer 38개는 다음을 검사한다.

- `{}`와 `()` entry에서 첫 필드 앞, `=` 앞뒤, 쉼표 앞뒤, 마지막 값/쉼표 뒤 주석 14개.
- braced/quoted 값의 선두·중간 줄·인라인 `%`, escaped `%`, URL escape, 중첩 괄호 보존 12개.
- `#` 앞뒤와 양쪽 주석, 정의된 macro 연결 3개.
- 주석 속 가짜 macro가 실제 정의가 되지 않는 사례 1개.
- BOM·CRLF·탭·한글·여러 entry의 정확한 source.raw, 입력 바이트와 해시 보존 1개.
- 주석 속 가짜 구분자로 누락된 문법을 채울 수 없고 출력도 만들지 않는 malformed 사례 7개.

| 검증 | 실제 결과 | 판정 |
| --- | --- | --- |
| 같은 신규 회귀, 수정 후 | **40 passed**, 133 deselected, 0.88초 | 통과 |
| 전체 pytest | **577 passed, 63 subtests passed**, 38.50초 | 통과; 실패·error·skip 없음 |
| `python -m compileall -q scripts tests` | exit 0 | 통과 |
| `git diff --cached --check` | exit 0 | 통과 |
| 실제 Pandoc 식별 | Pandoc 3.9, Lua 5.4 | 확인 |
| 독립 설치의 BibTeX/JOSS CLI | 11개 호출, 예상 결과 전부 관측 | 통과 |
| 독립 설치의 기존 JOSS citation/image CLI | 26개 호출, 예상 결과 전부 관측 | 통과 |

환경은 Linux, Python 3.12.14, pyparsing 3.3.2, Pandoc 3.9다. `CI=true`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`로 실행했다. CI의 compile·실제 Pandoc·pytest 계약을 따라 검증했으며, 별도 lint/type-check 도구를 추가하지 않았다.

전체 회귀에는 metadata 그림·경로 이탈·심볼릭 링크·파일명/충돌·묶음 보호, metadata Cite/nocite·wildcard·중복과 기존 집계, Word 인용 판정과 그림 이동, 근거 witness, Git 환경 격리와 기존 도구 연결 검사가 포함된다. 실제 Pandoc/DOCX 실행과 테스트 대역으로 처리하는 Microsoft Word/PDF 부분은 구분한다.

읽기 전용 독립 diff 검토에서도 이번 범위의 blocker를 발견하지 못했다. 별도 검토자가 테스트를 재실행한 결과라고 주장하지 않는다.

## 독립 설치와 원문 보존

검증한 Git tree는 `274fc329c628611638387606d98175ece7ee5025`다. 이 문서를 추가하기 전의 실행 코드·테스트·배포 payload 상태다. 최종 커밋과 이 tree의 코드·테스트 바이트를 대조하고 문서만 추가됐는지 확인한다.

설치 검증 대상으로 `SKILL.md LICENSE requirements.txt scripts references assets`를 선택해 38개 파일을 ZIP에 넣었다. 체크아웃 밖의 임시 폴더에 풀고 PYTHONPATH를 제거, user site를 비활성화한 채 설치된 스크립트의 CLI를 호출했다. 실행 의존성은 기존 검증용 가상환경을 사용했으며, 새 네트워크 의존성 설치를 했다고 주장하지 않는다.

BibTeX/JOSS 11회는 정상 입력 6회, 원본 폴더 삭제 후 이동한 패키지의 재검사·재출력 2회, malformed 입력의 예상 exit 2 세 번이다. BOM·CRLF·원본 `%`·주석·macro가 포함된 `source.raw`, bibliography 전체 바이트, source_input_sha256, bibliography_sha256, manifest의 모든 파일 해시가 일치했다. metadata 그림과 Cite, nocite는 이 주석 입력과 함께 검사됐다.

별도 기존 JOSS 설치 회귀 26회는 누락 키 7종의 preflight exit 1/export exit 2, 정상·중복·빈 nocite와 이동 재출력의 exit 0을 확인했다. 합계 **37회 중 정상 exit 0은 20회, 의도된 거부는 17회**다. 의도된 비정상 종료를 실패한 테스트나 거짓 성공으로 표시하지 않는다. 설치 payload도 실행 전후 그대로다.

## 전체 수정 이력

| 단계 | 커밋·기준 | 수정 및 결과 | 실제 게시 여부 |
| --- | --- | --- | --- |
| 첫 회차 | PR #2 → `91ecd79` | 인용 판정 연결, 근거 witness 재검사, Git 환경 격리. 515 passed + 69 subtests | 원래 커밋은 로컬 보존 |
| 추가 1/5 | `91ecd79` → `154f400` | Word 그림 원본·상대 경로·바이트 보존과 이동 재변환. 558 passed + 69 subtests | 원래 커밋은 로컬 보존 |
| 추가 2/5 | main 전용 이식 `88c705d`, 게시 `1a0b33a` | 두 회차의 수정만 main의 기존 API로 이식. 로컬 452 passed + 63 subtests | **`1a0b33a` 게시됨** |
| 추가 3/5 | `1a0b33a` → `5b44535` | 실제 Pandoc metadata Image까지 수집·누락/경로 보호. 494 passed + 63 subtests | 미게시 |
| 추가 4/5 | `5b44535` → `0d64576` | metadata Cite·명시적 nocite의 없는 키 차단, `@*` 의미 구분. 537 passed + 63 subtests | 미게시 |
| 추가 5/5 | `0d64576` 위의 이번 로컬 커밋 | BibTeX 구조 위치의 `%` 주석 수용. 577 passed + 63 subtests | 미게시 |

`88c705d`와 실제 게시 `1a0b33a`는 동일한 parent와 tree를 갖는 다른 commit 객체다. 두 수정을 중복 적용한 이력이 아니다. PR 기능이 포함됐던 검토 후보 `813c98c`의 462 passed 결과는 최종 main 반영에서 제외했고 그 커밋도 보존했다. PR 기준 69 subtests와 main 기준 63 subtests는 기준 코드 차이이며 이번에 기존 테스트를 지운 결과가 아니다.

과거의 CLI push exit 128 실패 기록도 유지했다. 이후 승인된 tree를 GitHub connector로 게시한 결과가 실제 `1a0b33a`다.

## Windows와 실제 렌더링의 한계

[main `1a0b33a`의 실제 Windows 실행](https://github.com/andongmin94/paper-factory/actions/runs/42591750689)은 GitHub API 재확인 시 completed/success다. 해당 SHA의 기존 로그는 **451 passed, 1 skipped, 63 subtests passed**다. 이 결과를 새 미게시 세 커밋의 Windows 검증으로 재사용하지 않는다.

기존 Windows skip은 quiet 로그에 node ID와 사유가 없다. 동일 SHA의 수집 순서·소스에 근거하면 대소문자만 다른 file/directory 충돌 fixture가 Windows 파일시스템에서 만들어지지 않아 생략됐을 가능성이 높다. 이는 **추정**이며 `-vv -rs`의 실제 Windows 결과는 없다. 그 보호 조건이 Windows에서 통과했다고 단정하지 않는다.

| 항목 | 이번 회차 상태 |
| --- | --- |
| 미게시 세 변경의 Windows/Python 3.11 CI | 미실행; 게시·CI 실행 요청 없음 |
| 실제 Microsoft Word 자동화와 PDF 렌더링 | 미실행; Linux 로컬 회귀와 구분 |
| JOSS 공식 Inara/PDF·전 페이지 육안 검수 | 미실행; Pandoc AST/CSL·소스 패키지만 확인 |
| 고전 BibTeX/Biber 실행 | 미실행; 공식 소스와 Pandoc 동작을 구분 |
| 실제 투고·배포·릴리스 | 미실행 |

## 보존·복원 자료

기존 외부 검증 산출물 **228개**는 작업 시작과 검증 종료 사이에 바이트 수와 SHA-256이 모두 일치했다. 기존 refs도 새 커밋 작성 전 전부 그대로였다. 앞선 보고서·패치·ZIP·bundle·실패 로그를 덮어쓰지 않았다.

이번 `round6`에는 새 이름으로 다음을 보존한다. 실제 최종 해시·오프라인 복원 결과는 `handoff.json`, `restoration-verification.json`, `SHA256SUMS.txt`에서 확인한다.

- 실제 원격 main `1a0b33a` 이후의 **미게시 세 변경만 담은 누적 binary patch**.
- `0d64576` 이후 이번 수정만 담은 증분 patch.
- 검증한 38개 파일의 설치 ZIP.
- 이전 PR 기반·main 이식·제외된 후보를 포함한 전체 refs/이력 bundle.
- 이전 회차 기록과 이번 검증 기록을 함께 담은 최종 복원 ZIP.

복원 검사는 새 임시 저장소에서 bundle verify·오프라인 clone·fsck를 수행하고, base별 patch 적용 후 `git write-tree`가 최종 tree와 같은지 비교한다. ZIP 파일들의 바이트는 Git blob 및 실제 CLI에 사용한 설치 ZIP의 payload와 대조한다. 이력 bundle에는 PR #2의 보존 이력도 있지만, 설치 ZIP과 main 이후 누적 patch에는 미승인 PR 기능을 포함하지 않는다.

## 남은 문제와 기록만 한 후보

현재 원격 main에는 아직 metadata 그림·metadata 인용/nocite·이번 주석 수정이 없다. 이번 로컬 회귀에서 해당 범위의 미해결 blocker를 새로 발견하지 못했다. 세 변경의 게시와 Windows CI, PR #2의 통합, 실제 Word/Inara 출력은 별도 결정·검증으로 남는다.

**다음 후보는 malformed BibTeX의 오류 위치 개선이다.** 이번 이미 실행한 누락 쉼표 fixture는 올바르게 거부되지만 import·preflight·export 모두 `Invalid BibTeX at line 3, column 1: Expected end of text`로 entry 시작점을 보고한다. 실제 잘못된 필드의 위치를 안내하지 못해 진단이 거칠다. 이 관측만 기록했으며 새 테스트·구현·원인 탐색을 시작하지 않았다.

본문 밖 실제 Image/Cite 수집을 raw HTML/TeX 의존성이나 Pandoc 전체 BibLaTeX 문법 지원으로 확장하지 않았다. 미실행 렌더링과 문서상 비지원 범위를 이번 성공으로 보장하지 않는다.
