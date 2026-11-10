# JOSS metadata 그림 보존 검증

2026-11-09, 추가 지시 3/5. 최신 main `1a0b33ac0a350850d011a44d725a66a2c78ac42e`에서 JOSS metadata 그림 누락을 수정했다. 이번 변경은 별도 로컬 브랜치 `fix/joss-metadata-images`에 보존하며 원격 게시 승인을 포함하지 않는다.

## 기준과 보존

- 작업 시작과 완료 직전 읽기 전용 재확인에서 원격 main은 `1a0b33a`, 유일한 열린 Draft PR [#2](https://github.com/andongmin94/paper-factory/pull/2)의 head는 `659fa818fab67fae2259d758c4472e423fa157ed`로 동일했다.
- 기존 main 커밋과 PR 기반 `91ecd79` → `154f400`, main 이식 검토 커밋·패치·ZIP·검증 로그를 보존했다. 이전 handoff 세 개에 기록된 산출물 19개의 SHA-256을 재대조해 모두 일치했다.
- 최신 main의 추적 파일과 로컬 상위 경로에서 별도의 AGENTS.md·QUALITY.md·CONTRIBUTING.md를 발견하지 못했다. 사용자가 제공한 단순한 구현, 기존 의존성 활용, 호환 계층 금지 지침을 적용했다.
- PR #2의 head를 변경하거나 통합·충돌 해결을 수행하지 않았다. 새 PR 기능, 의존성, CI 설정, 별도 그림 처리 프레임워크를 추가하지 않았다.

## 입력 계약과 처리 방침

### 확인한 공식 근거

1. [JOSS paper format](https://joss.readthedocs.io/en/latest/paper.html)과 [현재 예제](https://joss.readthedocs.io/en/latest/example_paper.html)는 Markdown 원고와 YAML metadata를 사용하며 제목은 plain text로 작성하도록 안내한다. 제목은 인용 metadata에도 재사용된다.
2. [Pandoc YAML metadata 문서](https://pandoc.org/MANUAL.html#extension-yaml_metadata_block)는 metadata에 중첩된 목록·객체가 올 수 있고 문자열을 Markdown으로 해석한다고 설명한다.
3. 저장소가 참조하는 고정 Inara 버전의 [shared defaults](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/data/defaults/shared.yaml)는 `markdown` reader와 standalone 문서를 사용한다. [실제 템플릿](https://github.com/openjournals/inara/blob/88ee5d656f147d801448ce77ad8375619d383df6/data/templates/default.latex)은 abstract·include-before 등 metadata 슬롯을 소비한다.

현재 저장소 문서는 원고·BibTeX·참조 그림 보존을 약속하며 본문 그림만 대상으로 한정하지 않는다. 구현은 이미 metadata와 본문을 모두 파싱하지만 Image 수집에 본문만 전달했다.

**결정:** 실제 Pandoc AST의 본문과 YAML metadata에 나타나는 Image를 동일한 기존 검증·보존 경로로 처리한다. metadata 그림 전체를 새로 금지하지 않는다. 이것은 소스 의존성을 보존하는 결정이며 임의의 metadata field나 제목 그림을 JOSS가 허용한다는 판단은 아니다. 제목은 공식 지침에 따라 plain text로 작성해야 한다.

일반 경로 문자열, raw HTML/LaTeX의 외부 파일, Inara 실행 환경·출판사 자산까지 수집하는 계약은 추가하지 않았다. metadata 의미 검사, 인용 키 검사, 본문 단어 수와 실제 출판사 렌더링도 이번 변경 범위에 포함하지 않는다.

## 최소 구현

Production 변경은 `scripts/_publication_joss.py`의 Image 수집 한 곳과 설명 주석뿐이다.

```python
# Before
images = sorted({node["c"][-1][0] for node in _nodes(blocks) if node.get("t") == "Image"})

# After
images = sorted({node["c"][-1][0] for node in _nodes(document) if node.get("t") == "Image"})
```

기존 `_nodes()`는 dict/list를 재귀 순회하므로 MetaInlines·MetaBlocks·MetaList·MetaMap에 별도의 parser가 필요하지 않다. JOSS가 이미 파싱한 `markdown` AST를 활용하며 Word 전용 reader로 다시 파싱하지 않는다.

새로 발견한 metadata Image도 기존 resource root 선택, 상대경로·URI·예약 출력명 검사, symlink/junction 거부, 실제 파일·빈 파일·Pillow raster 검증, 원본 변경 검사, exclusive-create 복사와 manifest를 그대로 거친다. 원고·YAML·BibTeX·그림 바이트와 그림의 상대경로는 재작성하지 않는다.

## 실패 재현과 회귀

Production 수정 전에 실제 Pandoc 3.9로 새 42개 회귀를 실행했다.

```text
40 failed, 2 passed, 18 deselected in 3.38s
```

본문에 없는 metadata 그림을 무시해 image count 0으로 성공하거나, metadata에 없는 파일·외부 URL·이탈 경로를 넣어도 preflight와 export가 성공하는 것을 확인했다. 기존 코드가 이미 거부하던 symlink resource root와 실제 Image가 아닌 literal 예제 두 경우는 통과했다. 실패를 통과로 계산하지 않았다.

원래 제목의 `![Logo](missing-logo.png)` 재현도 유지했다. 이는 잘못된 입력이 성공하는 사례이며 정상 JOSS 제목 예제로 사용하지 않는다. 정상 보존 회귀의 제목은 plain text다.

새 회귀가 확인한 범위는 다음과 같다.

- 실제 Pandoc AST의 MetaInlines, MetaMap → MetaList → MetaBlocks 중첩, Image target.
- metadata 내부 또는 본문에 정의한 참조형 그림, metadata와 본문의 동일 target 중복, metadata에만 있는 별도 그림.
- 누락 파일의 preflight/export 거부와 파일명 진단, 새 출력·성공 manifest 미생성.
- 한글·공백·괄호·percent/hash 파일명, 한 번의 URL decoding, 원고 BOM/CRLF와 원본 바이트 보존.
- 명시적 resource directory 선택과 잘못된 fallback 방지.
- 경로 이탈·인코딩된 이탈·절대 경로·외부 URL·query/fragment·역슬래시·예약 출력명 거부.
- 파일·상위 디렉터리·resource root의 symlink, 빈 파일·디렉터리·손상 raster 거부.
- preflight와 export 도중 바뀐 metadata 그림의 감지.
- 출력 이동과 임시 원본 삭제 후 source preflight/re-export.
- 명시적으로 원고·서지·그림만 선택한 제출 묶음의 이동, 원본과 중간 export 삭제 후 재사용.
- Code·일반 문자열·raw HTML/LaTeX를 Image로 추정하지 않는 기존 경계.

동일한 AST target 문자열은 기존 set 의미에 따라 한 번 보존한다. 경로 alias의 image-count 정의를 새로 바꾸지는 않았다. metadata 내용을 본문 word count에 합산하지 않았으며 그 불변 조건도 검사했다.

## 검증 결과

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| 수정 전 새 회귀 | **40 failed, 2 passed, 18 deselected** | 실제 결함 재현, exit 1 |
| 수정 후 JOSS 모듈 | **60 passed** | 기존 18개 + 신규 42개, 6.02초 |
| 최종 전체 pytest | **494 passed, 63 subtests passed** | 31.37초, 실패·error·skip 없음 |
| 실제 Pandoc 식별 | **통과: Pandoc 3.9** | 기존 실행 파일 사용 |
| 스크립트 컴파일 | **통과** | `python -m compileall -q scripts` |
| working/staged diff 검사 | **통과** | `git diff --check`, `git diff --cached --check` |
| 독립 설치 ZIP·실제 CLI | **통과** | 38개 파일의 Git 바이트 대조, 예상 실패 2건과 정상·이동 후 실행 4건 |
| 기존 산출물 해시·커밋 보존 | **통과** | 이전 산출물 19개 및 원래 브랜치 이력 |
| 새 변경의 Windows CI | **미실행** | 로컬 작업만 승인됨; 원격 게시하지 않음 |
| 실제 Word/PDF | **미실행** | 이번 JOSS 경로의 출력 방식이 아님 |
| 실제 Inara/PDF·페이지 육안 확인 | **미실행** | 소스 패키지 검증과 구분 |

환경은 Linux, Python 3.12.14, pytest 9.2.0, Pandoc 3.9다. `CI=true`로 실제 Pandoc 검사를 필수화하고 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`로 무관한 plugin 자동 로딩을 비활성화했다. 새 의존성이나 설치 변경은 없다.

### 독립 설치 패키지

기존 설치 선택인 `SKILL.md LICENSE requirements.txt scripts references assets`의 38개 파일로 ZIP을 만들고 staged Git tree의 파일 바이트와 모두 대조했다. 별도 임시 디렉터리에 압축을 풀고 `PYTHONPATH`와 user site를 배제한 상태에서 실제 설치본 CLI를 실행했다. 템플릿 경로도 압축 해제한 패키지 안에 있음을 확인했다.

- 누락 metadata 그림: preflight와 export 각각 예상한 exit 2, 파일명 진단, 출력 미생성, 입력 바이트 불변.
- 정상 입력: preflight와 export 각각 exit 0. metadata 전용 그림과 metadata·본문이 공유하는 그림을 합계 2개 보존하며, 중복을 제거하고 원고·BibTeX·한글/공백 그림 경로·파일 바이트·manifest를 확인했다.
- 생성된 소스 패키지를 이동하고 임시 원본 폴더를 삭제한 뒤 preflight와 re-export 각각 exit 0. 동일한 그림 2개와 manifest 해시를 확인했다.
- 설치 파일과 ZIP 자체는 실행 전후 동일했고, 임시 입력과 설치 폴더는 검증 후 정리했다.

테스트한 ZIP SHA-256은 `3b5851d81a668af94ed10cff7658a76a187bf79fb3667d6b6aef53d2d14c1513`이다. 상세 결과는 `joss-installed-cli-verification.json`과 로그, 재현 스크립트 `verify_joss_install_package.py`에 보존했다. 소스 검사 통과만 확인했으며 `submission_ready=false`, PDF·DOCX 없음, 실제 Inara/Word 호출 없음도 검사했다. 이를 Inara/PDF 렌더링 성공으로 해석하지 않는다.

### 재실행

프로젝트 의존성·pytest와 Pandoc이 준비된 저장소 루트에서 실행한다.

```bash
export CI=true
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python -m pytest -q tests/test_joss_export.py
python -m compileall -q scripts
python -m pytest -q
git diff --check
```

실패·성공 로그, JUnit XML, 실행 명령, AST probe와 보존 검사는 별도 `paper-factory-verification/round4/`에 저장하며 이전 결과를 덮어쓰지 않는다.

## 기존 Windows skip 설명

**확인한 사실:** 기존 main `1a0b33a`의 Windows/Python 3.11.9 CI는 451 passed, 1 skipped, 63 subtests passed였다. 로그 진행 기호 452개 중 유일한 skip은 91번째다. 같은 HEAD를 Linux에서 `--collect-only`로 수집했을 때 91번째는 `test_image_file_and_directory_casefold_collisions_are_rejected[paths2]`였다.

그 fixture는 `figures` 파일과 `FIGURES/plot.png`의 부모 디렉터리를 만들다가 FileExistsError/NotADirectoryError가 나면 건너뛴다. 따라서 대소문자를 구분하지 않는 디렉터리에서 fixture를 구성할 수 없어 skip됐다는 설명과 일치한다.

**추정의 한계:** 원격 `pytest -q` 로그에는 node ID와 개별 사유가 없다. 소스와 수집 순서가 강하게 뒷받침하는 추정이며 새 Windows 실행 결과가 아니다. 이 특정 충돌 거부 분기가 Windows에서 실행되어 통과했다고 주장하지 않는다. 확정하려면 이후 Windows에서 해당 항목을 `-vv -rs`로 실행해 사유를 남겨야 한다. 기존 Windows CI 성공을 이번 새 커밋의 검증으로 재사용하지 않는다.

## 다음 실제 문제와 필요한 결정

**JOSS metadata의 미정의 citation key도 본문 전용 검사에서 빠진다.** 실제 Pandoc으로 본문 `[@retained]`를 유지하고 YAML abstract에 `[@missing]`를 추가했다. `paper.bib`에는 retained만 정의했다.

| 입력 | 기존 main | 이번 그림 수정본 |
| --- | --- | --- |
| metadata abstract의 `[@missing]` | preflight/export 성공 | preflight/export 성공 |
| 같은 `[@missing]`을 본문으로 이동 | preflight 실패·export 차단 | preflight 실패·export 차단 |

전체 AST에는 missing과 retained가 있지만 도구가 보고하는 citation keys는 retained뿐이다. 두 checkout에서 실제 재현했으므로 이번 그림 수정이 만든 회귀가 아니다. Inara/PDF에서 어떤 결과가 나오는지는 실행하지 않았다.

다음에는 metadata의 Cite도 정의된 BibTeX key 검사에 포함하는 범위를 정해야 한다. [Pandoc이 지원하는 `nocite`와 `@*`](https://pandoc.org/MANUAL.html#including-uncited-items-in-the-bibliography) 같은 특수 의미를 일반 인용키와 구분하고, 중첩·중복·실제 누락 사례를 함께 검증하는 것이 필요하다. 이번에는 citation 수집이나 정책을 변경하지 않았다.

기존 JOSS 파일 보호가 Word 경로의 모든 Windows 파일명·casefold 정책과 같다고 주장하지 않는다. case-sensitive 예약명 검사, casefold 파일/디렉터리 충돌의 선제 진단 등은 기존 구현의 별도 검토 범위다. 이번 변경은 metadata Image를 기존 JOSS 보호에 연결한 것이다.

## 변경 파일과 인계

- 구현: `scripts/_publication_joss.py`
- 회귀: `tests/test_joss_export.py`
- 계약 문서: `references/joss.md`, `references/tools.md`
- 검증 기록: 이 문서

main 기준 증분 패치와 이전 main 반영까지 포함한 누적 패치, 설치 ZIP, 로컬 이력 bundle을 새 파일명으로 보존한다. 이번 새 변경의 원격 게시에는 별도 승인이 필요하다. PR #2의 통합과 충돌 해결은 이번 회차 범위에 포함하지 않는다.
