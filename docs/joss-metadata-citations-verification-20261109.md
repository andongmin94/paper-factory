# JOSS metadata 인용 키 검증

2026-11-09, 추가 지시 4/5. 이전 metadata 그림 수정 `5b44535be758d9b667baa30eaffe72ad84f68b50` 위에서 metadata의 미정의 citation key 누락을 개선했다. 브랜치는 `fix/joss-metadata-citations`이며 이번 변경은 로컬에만 보존한다.

## 기준과 중복 확인

- 작업 시작과 완료 전 원격 읽기에서 main은 `1a0b33ac0a350850d011a44d725a66a2c78ac42e`, 유일한 열린 Draft PR #2의 head는 `659fa818fab67fae2259d758c4472e423fa157ed`로 동일했다.
- main, PR #2, `5b44535`의 기존 인용 검사는 모두 본문 `blocks`의 Cite만 수집하는 동일한 코드였다. PR #2의 구조화된 저자 이름·raw 그림 등 다른 변경은 이번 작업에 가져오지 않았다.
- 기존 `91ecd79` → `154f400`, 게시한 main `1a0b33a`, 이전 main 이식 검토 이력과 `5b44535`의 브랜치·패치·ZIP·로그를 보존했다. 이전 인계 기록에 기재된 53개 해시를 다시 확인했고 모두 일치했다. 이번 시작 시 기존 파일 116개의 별도 보존 스냅샷도 만들었다.
- 추적 파일과 작업 디렉터리 상위에서 별도의 AGENTS.md·QUALITY.md·CONTRIBUTING.md를 발견하지 못했다. 사용자가 제공한 단순한 구현, 기존 의존성 활용, 호환 계층 금지 지침을 적용했다.
- PR 통합·충돌 해결, 원격 게시·병합·배포·릴리스·설정 변경은 수행하지 않았다.

## 공식 계약과 도구의 검사 정책

확인한 1차 자료:

- [JOSS citations](https://joss.readthedocs.io/en/latest/paper.html#citations): 서지 데이터를 paper.bib에 보관하고 BibLaTeX 또는 BibTeX와 Pandoc 인용 문법을 사용한다.
- [Pandoc YAML metadata](https://pandoc.org/MANUAL.html#extension-yaml_metadata_block): 문자열은 Markdown으로 파싱하며 metadata의 목록과 객체는 중첩될 수 있다.
- [Pandoc nocite](https://pandoc.org/MANUAL.html#including-uncited-items-in-the-bibliography): 최상위 nocite는 본문에 표시하지 않을 서지 항목을 선택하며 @*는 전체 항목을 선택한다.
- [Pandoc bibliographic data](https://pandoc.org/MANUAL.html#specifying-bibliographic-data): 일반 Pandoc은 inline CSL references도 사용하며 외부 서지와 같은 ID가 있으면 inline 값이 우선한다.

실제 Pandoc 3.9의 파싱 전용 AST와 일반 citeproc JSON 출력을 11개 입력에서 관찰했다. 일반 metadata의 미정의 Cite는 경고를 내지만, 최상위 nocite의 없는 명시 key는 경고 없이 무시했다. nocite의 @*와 없는 key를 함께 적어도 전체 서지를 선택하고 없는 key는 무시했다. 본문·일반 metadata·notes.nocite의 @*는 전체 선택자가 아니며, 이 입력에서는 출력 형태가 없는 인용이라는 경고를 냈다.

**이번 결정:** 기존 paper.bib 기반 소스 검사에 metadata Cite와 명시적 nocite key를 포함한다. 최상위 nocite의 실제 Cite ID `*`만 선택자로 제외한다. 사용자가 명시한 없는 key는 wildcard와 함께 있어도 차단한다. 이는 citeproc가 조용히 무시하는 nocite 오탈자까지 진단하는, 의도적으로 더 엄격한 소스 검사다. 해당 거부를 Inara/PDF 실패의 재현이라고 해석하지 않는다.

| 입력 범위 | 처리 |
| --- | --- |
| 본문·References 구간의 실제 Cite | paper.bib에 key가 있어야 함 |
| abstract·중첩 metadata·references 목록 내부의 실제 Cite | 동일한 key 검사 |
| 최상위 nocite의 명시 key | paper.bib에 있어야 함; 중복은 한 번 검사 |
| 최상위 nocite의 @* | 전체 서지 선택자로 인정; literal Bib key로 요구하지 않음 |
| 일반 metadata 또는 중첩 notes.nocite의 @* | 선택자 예외 없음; 없는 key `*`로 진단 |
| 빈 값·코드·raw 콘텐츠·escaped literal·일반 문자열 | 실제 Cite가 없으면 key를 추정하지 않음 |

기존 도구의 본문 인용 존재 조건은 유지한다. Pandoc은 nocite만 있는 문서도 처리할 수 있지만 이 도구의 기존 JOSS preflight에서는 실제 본문 인용이 필요하다. 이를 JOSS가 명시한 독립적 편집 규칙이라고 주장하지 않는다.

집계도 유지한다. `metrics.citation_keys`는 본문 Cite ID의 정렬된 중복 없는 목록이고, `metrics.reference_count`는 paper.bib의 전체 record 수다. metadata/nocite를 추가해 이 집계를 늘리거나 실제 렌더링된 참고문헌 수로 바꾸지 않는다. YAML·References·code를 제외하는 본문 단어 수 산정도 그대로다.

inline CSL은 작성한 원고 바이트에 보존하지만 별도의 key-definition database로 해석하는 지원을 추가하지 않았다. 일반 metadata id는 Cite로 추정하지 않으며, paper.bib에 없는 key를 inline references로 충족하는 것으로 판정하지 않는다. 현재 저장소의 paper.bib 기반 검사 범위와 Pandoc의 더 넓은 입력 기능을 구분했다.

## 최소 구현과 보호 조건

production 변경 파일은 scripts/_publication_joss.py 하나다. 기존 재귀 순회로 실제 Cite ID만 모으는 작은 `_citation_keys()` 함수를 두고 다음 세 집합을 분리했다.

1. 본문 Cite: 기존 집계와 본문 인용 존재 조건에 사용한다.
2. 최상위 nocite를 제외한 metadata Cite: 중첩된 metadata를 재귀 검사한다.
3. 최상위 nocite의 Cite: `*`만 제거하고 명시 key를 검사한다.

세 집합에서 paper.bib key를 뺀 결과를 정렬·중복 제거해 동일한 citation_keys 항목의 실패 사유로 기록한다. preflight의 실패 보고서를 export가 기존 방식으로 소비하므로 실패 입력의 출력 디렉터리를 만들지 않는다. 진단에는 기존 본문 인용 요구 조건도 명시했다.

새 파서·정규식 인용 추정·의존성·PR 기능을 추가하지 않았다. 실제 Image 수집, 경로·symlink·파일·원본 변경 검사, 바이트 보존·복사·manifest 및 Word/연구 모듈은 변경하지 않았다. 기존 JOSS 테스트 함수 25개가 동일하고, 기존 Image/export 로직과 metrics 식이 동일함도 소스 대조로 확인했다.

## 전후 회귀

production 변경 전 신규 43개를 실제 Pandoc으로 실행했다.

    16 failed, 27 passed, 60 deselected in 6.12s

metadata 누락 key의 preflight 성공·export 성공과 nocite 누락 무시를 재현했다. 본문·References의 기존 차단과 정상 wildcard·빈 값·비인용 literal 경계는 이미 통과했다. 이 결과는 결함 재현이며 성공한 회귀 검사로 표시하지 않는다.

동일한 테스트 파일을 유지한 채 production을 최소 수정한 뒤 전체 JOSS 모듈은 다음과 같았다.

    103 passed in 10.79s

검사 범위:

- 실제 MetaInlines·MetaBlocks·MetaMap·MetaList의 Cite와 abstract·중첩 metadata·references 목록·본문·References 구간의 누락.
- 일반 metadata의 올바른 명시 key와 중복, metadata 전용 key의 유효성, 본문 인용 목록·전체 Bib 수·word count 불변.
- nocite의 명시 key·wildcard·혼합·중복·목록, 빈 문자열·null·빈 목록·빈 map·빈 block scalar.
- nocite 내부 중첩 구조, 최상위 밖에 놓인 nocite 이름과 wildcard, wildcard가 다른 scope의 오류를 숨기지 못하는 조건.
- metadata/nocite만으로 기존 본문 인용 조건을 대체하지 않음, wildcard가 중복 Bib key 검사를 우회하지 않음.
- 여러 위치에 반복된 미정의 key를 한 번씩 정렬해 보고함.
- Code·raw HTML attribute·raw TeX·escaped literal·일반 문자열의 비인용 경계.
- 정상 원고의 BOM/CRLF 및 원본 바이트·manifest 보존, 실패 시 출력 미생성.

## 전체 검증 결과

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| 수정 전 신규 회귀 | **16 failed, 27 passed** | 60 deselected, exit 1; 결함 재현 |
| 수정 후 JOSS 모듈 | **103 passed** | 이전 60개 + 신규 43개 |
| 전체 pytest | **537 passed, 63 subtests passed** | 40.20초, 실패·error·skip 없음 |
| 실제 Pandoc 식별 | **통과, 3.9** | 기존 설치 실행 파일 사용 |
| compileall | **통과** | python -m compileall -q scripts |
| working/staged diff 검사 | **통과** | git diff --check 및 --cached --check |
| 독립 ZIP CLI 전후 | **예상 결과 확인** | 수정 전/후 각각 26개 호출; 아래에 실패·성공 구분 |
| 새 변경의 Windows CI | **미실행** | 이번 변경은 로컬만 보존 |
| 실제 Word/PDF | **미실행** | 기존 Word 모듈의 로컬 회귀와 구분 |
| 실제 Inara/PDF 및 페이지 육안 검수 | **미실행** | AST/citeproc JSON·소스 패키지 검사와 구분 |

환경: Linux, Python 3.12.14, pytest 9.2.0, Pandoc 3.9. CI=true, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1을 적용했다. 기존 설치와 의존성을 사용했으며 새 패키지나 환경 설정을 추가하지 않았다.

기존 main `1a0b33a`의 Windows 결과 451 passed, 1 skipped, 63 subtests passed는 과거 기록이다. 이번 커밋의 Windows 검증으로 재사용하지 않았다. 기존 skip에 대한 소스·수집 순서 기반 추정과 그 한계는 이전 metadata 그림 검증 문서와 round4 기록에 그대로 남아 있다.

### 독립 설치 CLI

기존 설치 선택 SKILL.md, LICENSE, requirements.txt, scripts, references, assets로 만든 38개 파일의 ZIP을 Git 바이트와 대조했다. 별도 임시 디렉터리에 압축 해제하고 PYTHONPATH·user site를 배제해 설치본 CLI를 실행했다. template 경로도 설치본 내부임을 확인했다.

- 수정 전 `5b44535`: 5종류의 metadata/nocite 누락 입력에서 preflight/export 합계 10개 호출이 잘못 exit 0으로 통과했다. 본문·References 누락 대조군은 기존대로 차단됐다.
- 수정 후: abstract·중첩 metadata·references 목록·명시적 nocite·wildcard 동반 nocite·본문·References의 누락 7종을 preflight exit 1, export exit 2로 각각 차단했다. 합계 14개 예상 거부이며 실패 export는 출력 디렉터리를 만들지 않았다.
- 정상 명시 nocite·wildcard·혼합 중복·빈 문자열·빈 목록은 preflight/export 모두 exit 0이었다.
- 혼합 입력의 소스 패키지를 이동하고 원본 폴더를 삭제한 뒤 preflight와 re-export도 exit 0이었다. 합계 정상 실행 12개다.
- 원고·Bib·metadata 그림·본문 그림의 원본 바이트, 같은 상대경로, manifest 해시를 확인했다. reference_count=4, body citation_keys=[retained], image_count=2를 유지했다.
- submission_ready=false, PDF·DOCX 없음, Inara/Word 미호출을 확인했다. 설치 payload와 archive는 실행 전후 동일했고 임시 fixture는 제거했다.

테스트한 staged tree는 `71f5e2642409bcafb2cab4ad72f2282bb4a4e9d8`, 수정 후 ZIP SHA-256은 `5f1b30921847eae915df4862879c227abc020d27fd7245244685240c4535356a`다. 최종 커밋 ZIP의 payload와 대조한 결과는 별도 인계 기록에 남긴다.

### 재실행

프로젝트 의존성·pytest와 Pandoc이 준비된 저장소 루트에서 실행한다.

    export CI=true
    export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
    python -m pytest -q tests/test_joss_export.py
    python -m compileall -q scripts
    python -m pytest -q
    git diff --check

실행 명령, RED/GREEN 로그와 JUnit XML, 독립 설치 재현 스크립트 및 JSON, 공식 계약 probe는 paper-factory-verification/round5에 보존했다. 이전 파일은 덮어쓰지 않는다.

## 다음 실제 문제

**필드 뒤에 붙인 BibTeX/BibLaTeX `%` 주석을 프로젝트 서지 파서가 거부한다.** 원고와 Bib 레코드를 고정하고 다음 한 줄의 주석 유무만 바꾸었다.

    title = {A Retained {Research} Tool}, % supplied annotation

실제 Pandoc 3.9의 biblatex와 bibtex reader는 --fail-if-warnings에서도 두 입력을 exit 0, 빈 stderr, 동일한 CSL record로 읽었다. 반면 프로젝트는 주석 없는 입력에서 JOSS preflight/export가 성공하고, 주석을 추가하면 두 경로 모두 다음 오류로 거부했다.

    Invalid BibTeX at line 1, column 1: Expected end of text

원격 main과 같은 `1a0b33a`, clean `5b44535`, 이번 인용 수정본에서 모두 재현했다. PR #2의 `_bibtex_records` 함수만 독립적으로 대조해도 동일하게 거부하므로 해당 PR에서 이미 해결된 기능은 아니다. 인용 검사에 도달하기 전 parse_bibliography에서 거부되며 이번 변경이 만든 회귀가 아니다.

다음에는 기존 pyparsing 기반 서지 파서의 entry 내부 주석 처리를 보완하는 최소 범위를 결정해야 한다. URL의 a%20b, escaped literal \%, braced/quoted 값, source.raw와 원본 bibliography 바이트는 보존해야 한다. 임의로 `%` 뒤를 지우는 전처리는 이 조건을 깨뜨린다. 이번에는 문제를 재현하고 기록했으며 서지 파서는 수정하지 않았다. Pandoc reader 통과를 실제 Inara/PDF 성공으로 해석하지 않는다.

## 변경 파일과 복원 자료

- scripts/_publication_joss.py: 실제 Cite 집합과 nocite 선택자 구분.
- tests/test_joss_export.py: 신규 43개 회귀, 기존 테스트 유지.
- references/joss.md, references/tools.md: 소스 검사 범위·집계·Pandoc과의 차이.
- 이 검증 문서.

증분 패치(5b44535 기준), 미게시 JOSS 두 회차 누적 패치(1a0b33a 기준), 앞선 main 반영까지 포함한 누적 패치(1aff3b7 기준), 설치 ZIP과 기존 브랜치를 포함한 Git bundle을 구분해 새 이름으로 보존한다. 각 패치는 해당 기준점에 실제 적용해 최종 Git tree와 대조하고, artifact hash와 로컬 커밋은 round5/handoff.json에 기록한다. 이 새 변경의 원격 반영에는 별도 승인이 필요하다.
